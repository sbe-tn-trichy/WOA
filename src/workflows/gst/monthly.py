"""Monthly GST movements versus following-month cash tax debits."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from calendar import monthrange
from decimal import Decimal
from typing import cast
from workflows.core.matching import to_finite_decimal


@dataclass(frozen=True)
class MonthlyGSTCheck:
    tax: str
    output: Decimal
    input: Decimal
    net: Decimal
    next_month_cash_debits: Decimal
    difference: Decimal


def month_bounds(year: int, month: int) -> tuple[str, str]:
    return date(year, month, 1).isoformat(), date(year, month, monthrange(year, month)[1]).isoformat()


def gst_movements(report: Mapping[str, object]) -> dict[str, tuple[Decimal, Decimal]]:
    raw_ctx = report.get('page_context')
    context = raw_ctx if isinstance(raw_ctx, Mapping) else {}
    if report.get('code') != 0 or str(context.get('cash_based')).lower() != 'false':
        raise ValueError('Successful accrual trial balance required')
    names = {n for tax in ('CGST', 'SGST', 'IGST', 'CESS') for n in (f'Input {tax}', f'Output {tax}', f'Cash Ledger : {tax} Tax')}
    found: dict[str, tuple[Decimal, Decimal]] = {}

    def visit(nodes: Sequence[object]) -> None:
        for node_obj in nodes:
            if not isinstance(node_obj, Mapping):
                continue
            node = cast(Mapping[str, object], node_obj)
            name = str(node.get('name') or '')
            if name in names:
                if name in found:
                    raise ValueError('Ambiguous GST account: ' + name)
                values_obj = node.get('values', [node])
                values = values_obj if isinstance(values_obj, list) else [node]
                if len(values) != 1 or not isinstance(values[0], Mapping):
                    raise ValueError('Single-period trial balance required')
                val_row = cast(Mapping[str, object], values[0])
                d_amt = to_finite_decimal(val_row.get('net_debit'))
                c_amt = to_finite_decimal(val_row.get('net_credit'))
                if d_amt is None or c_amt is None:
                    raise ValueError('Missing or invalid GST debit/credit: ' + name)
                found[name] = (d_amt, c_amt)
            children = node.get('accounts') or node.get('account_transactions')
            if isinstance(children, Sequence):
                visit(children)

    root = report.get('trialbalance')
    if not isinstance(root, (dict, list)):
        raise ValueError('Trial balance rows missing')
    visit([root] if isinstance(root, dict) else root)
    if names - found.keys():
        raise ValueError('Missing GST accounts: ' + ', '.join(sorted(names - found.keys())))
    return found


def check_monthly_gst(current: Mapping[str, object], following: Mapping[str, object]) -> list[MonthlyGSTCheck]:
    raw_curr_ctx = current.get('page_context')
    current_context = raw_curr_ctx if isinstance(raw_curr_ctx, Mapping) else {}
    raw_next_ctx = following.get('page_context')
    next_context = raw_next_ctx if isinstance(raw_next_ctx, Mapping) else {}
    start_str = str(current_context.get('from_date') or '')
    if not start_str:
        raise ValueError('Missing from_date in current context')
    start = date.fromisoformat(start_str)
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    if (current_context.get('from_date'), current_context.get('to_date')) != month_bounds(start.year, start.month) or (next_context.get('from_date'), next_context.get('to_date')) != month_bounds(year, month):
        raise ValueError('Consecutive complete calendar months required')
    now, later = gst_movements(current), gst_movements(following)
    rows = []
    for tax in ('CGST', 'SGST', 'IGST', 'CESS'):
        debit, credit = now[f'Output {tax}']; output = credit - debit
        debit, credit = now[f'Input {tax}']; input_tax = debit - credit
        cash = later[f'Cash Ledger : {tax} Tax'][0]
        net = output - input_tax
        rows.append(MonthlyGSTCheck(tax, output, input_tax, net, cash, cash - net))
    return rows
