"""Read-only GST cash-ledger versus net GST balance reconciliation."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, cast

from utils.file_utils import json
from workflows.audited_financials.reports import _firm_rule


class BooksRequestClient(Protocol):
    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Mapping[str, object] | None = None,
        json: Mapping[str, object] | None = None,
    ) -> object: ...


@dataclass(frozen=True)
class GSTCashLedgerCheck:
    tax: str
    cash_ledger: Decimal
    output_gst: Decimal
    input_gst: Decimal
    expected: Decimal
    difference: Decimal
    mismatch: bool


def check_gst_cash_ledger(report: Mapping[str, object], *, tolerance: Decimal = Decimal('0.01')) -> list[GSTCashLedgerCheck]:
    """Compare closing balance-sheet amounts; difference is cash minus net GST.

    Uses Tax cash ledgers only, excluding interest and late fees. Input and cash
    balances use Books asset presentation; output uses liability presentation.
    This is the requested balance equality, not a verification of filed returns.
    """
    if not tolerance.is_finite() or tolerance < 0:
        raise ValueError('Tolerance must be finite and nonnegative')
    if report.get('code') != 0 or not isinstance(report.get('balance_sheet'), list):
        raise ValueError('Successful Books balance sheet required')
    raw_ctx = report.get('page_context')
    context = raw_ctx if isinstance(raw_ctx, Mapping) else {}
    if str(context.get('cash_based')).lower() != 'false':
        raise ValueError('Accrual balance sheet required')
    amounts: dict[str, Decimal] = {}
    target_names = {name for tax in ('CGST', 'SGST', 'IGST', 'CESS')
                    for name in (f'Cash Ledger : {tax} Tax', f'Output {tax}', f'Input {tax}')}

    def visit(nodes: Sequence[Mapping[str, object]]) -> None:
        for node in nodes:
            name = str(node.get('name') or '')
            if name in target_names and name in amounts:
                raise ValueError('Ambiguous account name: ' + name)
            amount = Decimal(str(node.get('total', '0')))
            if not amount.is_finite():
                raise ValueError('Non-finite balance: ' + name)
            if name in target_names:
                amounts[name] = amount
            children = node.get('account_transactions')
            if isinstance(children, Sequence):
                visit(cast(Sequence[Mapping[str, object]], children))

    raw_bs = report.get('balance_sheet')
    visit(cast(Sequence[Mapping[str, object]], raw_bs) if isinstance(raw_bs, Sequence) else [])
    checks = []
    for tax in ('CGST', 'SGST', 'IGST', 'CESS'):
        names = (f'Cash Ledger : {tax} Tax', f'Output {tax}', f'Input {tax}')
        missing = [name for name in names if name not in amounts]
        if missing:
            raise ValueError('Missing GST accounts: ' + ', '.join(missing))
        cash, output, input_tax = (amounts[name] for name in names)
        expected = output - input_tax
        difference = cash - expected
        checks.append(GSTCashLedgerCheck(tax, cash, output, input_tax, expected, difference, abs(difference) > tolerance))
    return checks


def fetch_gst_cash_ledger_report(books: BooksRequestClient, *, from_date: str, to_date: str, firm: str | None = None) -> Mapping[str, object]:
    if date.fromisoformat(from_date) > date.fromisoformat(to_date):
        raise ValueError('Start date must not follow end date')
    rule = _firm_rule(firm, None)
    raw_report = books.request('GET', 'reports/balancesheet', params={
        'filter_by': 'TransactionDate.CustomDate', 'from_date': from_date,
        'to_date': to_date, 'cash_based': 'false', 'show_rows': 'all',
        'is_expand': 'true', 'rule': json.dumps(rule)})
    report = raw_report if isinstance(raw_report, Mapping) else {}
    raw_ctx = report.get('page_context')
    context = raw_ctx if isinstance(raw_ctx, Mapping) else {}
    if context.get('to_date') != to_date:
        raise ValueError('Books report date does not match')
    raw_applied = context.get('rule')
    applied = raw_applied if isinstance(raw_applied, Mapping) else {}
    applied_cols = applied.get('columns')
    applied_list = applied_cols if isinstance(applied_cols, list) else []
    expected_cols = rule.get('columns')
    expected_list = expected_cols if isinstance(expected_cols, list) else []
    if applied.get('criteria_string') != rule.get('criteria_string') or any(
        any(actual.get(k) != expected.get(k) for k in ('index', 'field', 'value', 'comparator', 'group'))
        for actual, expected in zip(applied_list, expected_list)
        if isinstance(actual, Mapping) and isinstance(expected, Mapping)
    ) or len(applied_list) != len(expected_list):
        raise ValueError('Books report location scope does not match')
    return report
