"""Read-only audited XLSX comparison using the reviewed column-B statement template."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal as D
from pathlib import Path
from collections.abc import Iterator, Mapping, Sequence
from typing import cast, Protocol
from utils.file_utils import json
from utils.file_utils import yaml
from zoho.books.custom.reports import Reports
from zoho.core_sdk.base_client import BaseZohoClient
from .reports import _firm_rule

@dataclass(frozen=True)
class ComparisonPeriod:
    from_date: str
    to_date: str

    def __post_init__(self) -> None:
        if date.fromisoformat(self.from_date) > date.fromisoformat(self.to_date):
            raise ValueError('Period start must not follow period end')

@dataclass(frozen=True)
class ComparisonResult:
    markdown: str
    net_profit_difference: D
    assets_difference: D

class BooksReportClient(Protocol):

    def request(self, method: str, endpoint: str, *, params: dict[str, object] | None = None) -> object:
        ...
REPORT_KEYS = {'profitandloss': 'profit_and_loss', 'balancesheet': 'balance_sheet', 'trialbalance': 'trialbalance'}

def validate_report(report: Mapping[str, object], name: str, period: ComparisonPeriod) -> None:
    context_obj = report.get('page_context')
    context = context_obj if isinstance(context_obj, Mapping) else {}
    if report.get('code') != 0:
        raise ValueError(f"Books {name} failed: {report.get('message')}")
    if context.get('to_date') != period.to_date or str(context.get('cash_based')).lower() != 'false':
        raise ValueError(f'Books {name} date or accrual basis does not match')
    if name != 'balancesheet' and context.get('from_date') != period.from_date:
        raise ValueError(f'Books {name} start date does not match')
    if not isinstance(report.get(REPORT_KEYS[name]), (list, Mapping) if name == 'trialbalance' else list):
        raise ValueError(f'Books {name} rows are missing')

def fetch_comparison_reports(client: BooksReportClient, period: ComparisonPeriod, excluded_location_ids: tuple[str, ...] | None=None, *, firm: str | None=None, firm_config: Path | None=None) -> dict[str, Mapping[str, object]]:
    rule: dict[str, object] | None = _firm_rule(firm, firm_config) if excluded_location_ids is None else ({'columns': [{'index': 1, 'field': 'location_name', 'value': list(excluded_location_ids), 'comparator': 'not_in', 'group': 'branch'}], 'criteria_string': '1'} if excluded_location_ids else None)
    reports: dict[str, Mapping[str, object]] = {}
    for name in REPORT_KEYS:
        for filtered in [True, False] if name != 'trialbalance' else [True]:
            params: dict[str, object] = {'filter_by': 'TransactionDate.CustomDate', 'from_date': period.from_date, 'to_date': period.to_date, 'cash_based': 'false', 'show_rows': 'all', 'is_expand': 'true'}
            if filtered and rule:
                params['rule'] = json.dumps(rule)
            if name == 'trialbalance':
                rule_val = params.get('rule')
                report = dict(Reports(cast(BaseZohoClient, client)).trial_balance(from_date=period.from_date, to_date=period.to_date, rule=str(rule_val) if rule_val is not None else None, show_rows='all'))
            else:
                raw_resp = client.request('GET', 'reports/' + name, params=params)
                report = dict(raw_resp) if isinstance(raw_resp, Mapping) else {}
            validate_report(report, name, period)
            if filtered and rule:
                page_ctx = report.get('page_context')
                applied = page_ctx.get('rule') if isinstance(page_ctx, Mapping) else None
                rule_cols = rule.get('columns') if isinstance(rule, Mapping) else None
                applied_cols = applied.get('columns') if isinstance(applied, Mapping) else None
                if (not isinstance(applied, Mapping) or not isinstance(rule, Mapping)
                        or applied.get('criteria_string') != rule.get('criteria_string')
                        or not isinstance(applied_cols, list) or not isinstance(rule_cols, list)
                        or len(applied_cols) != len(rule_cols)
                        or any(not isinstance(actual, Mapping) or not isinstance(expected, Mapping)
                               or any(actual.get(key) != expected.get(key)
                                      for key in ('index', 'field', 'value', 'comparator', 'group'))
                               for expected, actual in zip(rule_cols, applied_cols))):
                    raise ValueError(f'Books {name} did not echo the requested location scope')
            reports[name if filtered else name + '-all-locations'] = report
    return reports

def read_audited_workbook(source: Path) -> dict[str, list[tuple[object, ...]]]:
    from python_calamine import CalamineWorkbook
    workbook = CalamineWorkbook.from_path(source)
    try:
        sheets: dict[str, list[tuple[object, ...]]] = {}
        for name in workbook.sheet_names:
            rows: list[tuple[object, ...]] = []
            for row in workbook.get_sheet_by_name(name).to_python(skip_empty_area=False):
                tuple_row: tuple[object, ...] = tuple(None if value == "" else value for value in row)
                rows.append(tuple_row)
            sheets[name] = rows
    finally:
        workbook.close()
    for sheet, minimum_rows in [('Trading & P&L', 39), ('Balance Sheet', 30)]:
        if sheet not in sheets or len(sheets[sheet]) < minimum_rows:
            raise ValueError(f'Source must contain the reviewed {sheet} column-B template')
    return sheets

def load_accounting_mapping(path: Path) -> dict[str, object]:
    mapping = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    if not isinstance(mapping, dict) or any((not isinstance(mapping.get(key), dict) for key in ('calculations', 'pnl_expense_accounts', 'balance_sheet_accounts'))):
        raise ValueError('Mapping needs calculations, pnl_expense_accounts and balance_sheet_accounts')
    return mapping

def compare_audited_financials(s: Mapping[str, list[tuple[object, ...]]], reports: Mapping[str, Mapping[str, object]], config: Mapping[str, object], period: ComparisonPeriod, *, source_name: str, snapshot_description: str='saved API responses') -> ComparisonResult:
    """Compare the supported audited template using reviewed YAML account groupings."""
    for key, report in reports.items():
        validate_report(report, key.removesuffix('-all-locations'), period)

    calculations = config.get('calculations')
    if not isinstance(calculations, Mapping):
        raise ValueError('Missing calculations in config')
    pnl_expense_accounts = config.get('pnl_expense_accounts')
    if not isinstance(pnl_expense_accounts, Mapping):
        raise ValueError('Missing pnl_expense_accounts in config')
    balance_sheet_accounts = config.get('balance_sheet_accounts')
    if not isinstance(balance_sheet_accounts, Mapping):
        raise ValueError('Missing balance_sheet_accounts in config')
    pnl_balance_cfg = config.get('balance_sheet_pnl_accounts')
    balance_sheet_pnl_accounts = pnl_balance_cfg if isinstance(pnl_balance_cfg, Mapping) else {}
    raw_excluded = config.get('excluded_pnl_expense_accounts')
    excluded_expenses: list[str] = [str(x) for x in raw_excluded] if isinstance(raw_excluded, Sequence) else []

    def flatten(nodes: Sequence[Mapping[str, object]], account_names: dict[str, object] | None = None) -> dict[str, D]:
        account_names = {} if account_names is None else account_names
        result: dict[str, D] = {}
        for n in nodes:
            name = str(n.get('name', ''))
            amount = D(str(n['total']))
            if not amount.is_finite():
                raise ValueError('Non-finite report amount')
            if n.get('account_id'):
                previous = account_names.get(name)
                if previous is not None and previous != n['account_id']:
                    raise ValueError('Ambiguous Books account name: ' + name)
                account_names[name] = n['account_id']
            result[name] = amount
            children = n.get('account_transactions', [])
            child_nodes = [c for c in children if isinstance(c, Mapping)] if isinstance(children, Sequence) else []
            result.update(flatten(child_nodes, account_names))
        return result
    required = set(REPORT_KEYS) | {'profitandloss-all-locations', 'balancesheet-all-locations'}
    if required - reports.keys():
        raise ValueError('Missing report snapshots: ' + ', '.join(sorted(required - reports.keys())))
    pl = reports['profitandloss']
    bs = reports['balancesheet']
    pl_raw = pl.get('profit_and_loss', [])
    bs_raw = bs.get('balance_sheet', [])
    pl_nodes: list[Mapping[str, object]] = [n for n in pl_raw if isinstance(n, Mapping)] if isinstance(pl_raw, Sequence) else []
    bs_nodes: list[Mapping[str, object]] = [n for n in bs_raw if isinstance(n, Mapping)] if isinstance(bs_raw, Sequence) else []
    a = flatten(pl_nodes)
    b = flatten(bs_nodes)

    def financial_rows(nodes: Sequence[object]) -> list[tuple[object, object, object, object]]:
        res: list[tuple[object, object, object, object]] = []
        for n in nodes:
            if not isinstance(n, Mapping):
                continue
            children = n.get('account_transactions', [])
            child_seq = children if isinstance(children, Sequence) else []
            res.append((n.get('account_id'), n.get('name'), n.get('total'), financial_rows(child_seq)))
        return res

    def get_rep_seq(rep_key: str, node_key: str) -> Sequence[object]:
        val = reports[rep_key].get(node_key, [])
        return val if isinstance(val, Sequence) else []

    same_scope = all((financial_rows(get_rep_seq(n, k)) == financial_rows(get_rep_seq(n + '-all-locations', k))
                      for n, k in [('balancesheet', 'balance_sheet'), ('profitandloss', 'profit_and_loss')]))

    def total(d: dict[str, D], names: Sequence[str]) -> D:
        missing = set(names) - d.keys()
        if missing:
            raise ValueError('Unknown mapped Books accounts: ' + ', '.join(sorted(missing)))
        return sum((d[n] for n in names), D(0))

    def value(tab: str, row: int) -> D:
        amount = D(str(s[tab][row - 1][1]))
        if not amount.is_finite():
            raise ValueError(f'Invalid audited amount at {tab}!B{row}')
        return amount

    def f(v: object) -> str:
        return f'{v:,.2f}'

    def difference(v: D, *, debit_normal: bool) -> str:
        if v == 0:
            return '0.00'
        side = 'Dr' if (v > 0) == debit_normal else 'Cr'
        return f'{f(abs(v))} {side}'
    p = 'Trading & P&L'
    q = 'Balance Sheet'
    calculated: dict[str, D] = {}

    def calculate(name: str, active: tuple[str, ...] = ()) -> D:
        if name in active:
            raise ValueError('Circular calculation: ' + name)
        if name in calculated:
            return calculated[name]
        if name not in calculations:
            raise ValueError('Unknown derived calculation: ' + name)
        spec = calculations[name]
        if not isinstance(spec, Mapping):
            raise ValueError('Invalid calculation spec: ' + name)
        spec_accounts = spec.get('accounts')
        accounts_map = spec_accounts if isinstance(spec_accounts, Mapping) else {}
        amount = sum((total(a, [str(n)]) * D(str(coef)) for n, coef in accounts_map.items()), D(0))
        if 'path' in spec:
            spec_path = spec['path']
            if not isinstance(spec_path, Sequence) or not spec_path:
                raise ValueError('Empty report path: ' + name)
            nodes = pl_nodes
            node: Mapping[str, object] = {}
            for part in spec_path:
                matches = [n for n in nodes if n.get('name') == part]
                if len(matches) != 1:
                    raise ValueError('Ambiguous or missing report path: ' + str(part))
                node = matches[0]
                txs = node.get('account_transactions', [])
                nodes = [t for t in txs if isinstance(t, Mapping)] if isinstance(txs, Sequence) else []
            amount += D(str(node['total']))
        spec_derived = spec.get('derived')
        derived_map = spec_derived if isinstance(spec_derived, Mapping) else {}
        amount += sum((calculate(str(n), active + (name,)) * D(str(coef)) for n, coef in derived_map.items()), D(0))
        if not amount.is_finite():
            raise ValueError('Non-finite calculation: ' + name)
        calculated[name] = amount
        return amount
    sales, income, cogs, interest, freight, op, other_income, gross, operating = [calculate(n) for n in ['sales', 'income', 'cogs', 'interest', 'freight', 'op', 'other_income', 'gross', 'operating']]
    excluded_total = total(a, excluded_expenses)
    op -= excluded_total
    operating += excluded_total
    if not abs(income - cogs - a['Operating Expense'] - a['Non Operating Expense'] - a['Net Profit/Loss']) < D('.01'):
        raise ValueError('Financial arithmetic or report consistency check failed')
    if not abs(value(p, 8) - value(p, 15) - value(p, 32) - value(p, 37) - value(p, 39)) < D('.01'):
        raise ValueError('Financial arithmetic or report consistency check failed')
    if not abs(sum((value(q, r) for r in range(6, 18)), D(0)) - value(q, 18)) < D('.01'):
        raise ValueError('Financial arithmetic or report consistency check failed')
    if not abs(sum((value(q, r) for r in range(21, 28)), D(0)) - value(q, 28)) < D('.01'):
        raise ValueError('Financial arithmetic or report consistency check failed')
    if abs(value(q, 18) - value(q, 28)) >= D('.01'):
        raise ValueError('Audited balance sheet does not balance')
    if abs(sum((value(p, r) for r in (11, 12, 13, 14)), D(0)) - value(p, 15)) >= D('.01'):
        raise ValueError('Audited trading cost does not reconcile')
    input_gst = total(b, ['Input CGST', 'Input IGST', 'Input SGST'])
    gst_netting = input_gst if config.get('net_gst_in_balance_sheet_totals', False) else D(0)
    compared_assets = b['Assets'] - gst_netting
    text = [
        '# Audited financials versus Zoho Books',
        '',
        f'**Report created:** {datetime.now().astimezone().isoformat(timespec="seconds")}',
        '',
        f'Source: **{source_name}**, Trading & P&L and Balance Sheet tabs. Period: {period.from_date} to {period.to_date}. Books data: {snapshot_description}. All amounts INR; difference = Books minus audited. Saved workbook values used without recalculating formulas.',
        '',
        'Difference Dr/Cr shows the Books-minus-audited balance: excess assets or expenses are Dr; excess income, profit, liabilities or capital are Cr. Shortfalls reverse the side. Zero has no side. These are balance differences; an adjustment to align Books would use the opposite side.',
        '',
        f"Audited net profit **₹{f(value(p, 39))}**; Books **₹{f(a['Net Profit/Loss'])}**; difference **₹{difference(a['Net Profit/Loss'] - value(p, 39), debit_normal=False)}**.",
        f"Audited total assets **₹{f(value(q, 18))}**; Books **₹{f(compared_assets)}**; difference **₹{difference(compared_assets - value(q, 18), debit_normal=True)}**.",
        '',
        '## Scope and mapping',
        '',
        'Books reports use accrual basis and the requested location scope. ' + ('Filtered and unfiltered account amounts are identical, so branch scope remains unresolved. Account names do not establish transaction location.' if same_scope else 'Filtered and unfiltered account amounts differ; snapshots retain both scopes.'),
        'Comparisons use account names and the previously reviewed account groupings. Aggregated Other Expenses and unmapped lines require ledger-level confirmation. These differences do not establish individual posting errors.',
        '',
        '## P&L comparison',
        '',
        '| Audited line / cell | Audited | Books | Difference | Mapping / qualification |',
        '|---|---:|---:|---:|---|',
    ]
    used: set[str] = set()

    def row(tab: str, r: int, v: D, note: str) -> None:
        aud = value(tab, r)
        if tab == q and r == 6 and config.get('audited_gst_asset_to_fixed_assets', False):
            aud += value(q, 15)
            note += '; audited B6 includes GST asset B15 ' + f(value(q, 15))
        label = str(s[tab][r - 1][0])
        debit_normal = r < 21 if tab == q else r not in (6, 7, 8, 17, 34, 39)
        text.append(f'| {label} (B{r}) | {f(aud)} | {f(v)} | {difference(v - aud, debit_normal=debit_normal)} | {note} |')
    for r, v, note in [(6, sales, 'Sales accounts combined'), (7, other_income, 'All other operating and non-operating income'), (8, income, 'Total income'), (13, freight, 'Moved from Books operating expenses to trading cost'), (15, cogs + freight, 'Books COGS plus inward freight; purchases require inventory roll-forward'), (17, gross, 'Aligned to audited presentation'), (32, op, 'Books operating expenses excluding interest and inward freight'), (34, operating, 'Aligned to audited presentation'), (37, interest, 'Interest Expense'), (39, a['Net Profit/Loss'], 'Includes Books non-operating expense / credit')]:
        row(p, r, v, note)
    if excluded_expenses:
        text.append('Operating expense comparison excludes pending unmapped accounts: ' + ', '.join(excluded_expenses) + '. Books net profit and statement totals retain these balances.')
    mapping: dict[int, list[str]] = {
        int(k): [str(x) for x in v] if isinstance(v, Sequence) else []
        for k, v in pnl_expense_accounts.items()
    }
    for r, names in mapping.items():
        used.update(names)
        row(p, r, total(a, names), ', '.join(names))
    if sum((len(names) for names in mapping.values())) != len(used):
        raise ValueError('An expense account is mapped to multiple rows')
    other = op - total(a, list(used))
    row(p, 30, other, 'Residual operating expenses after mapped lines; proposed grouping')
    text += [
        '',
        '### Total COGS (B15) — all component lines',
        '',
        'Audited trading-cost components and the Books account breakdown are shown separately to retain both report presentations; the trial balance below preserves opening balances and account movements.',
        '',
        '| Audited component | Cell | Amount |',
        '|---|---|---:|',
    ]
    for r in [11, 12, 13, 14, 15]:
        text.append(f'| {s[p][r - 1][0]} | B{r} | {f(value(p, r))} |')
    text += [
        '',
        '| Books COGS account | Amount |',
        '|---|---:|',
    ]
    cogs_spec = calculations.get('cogs')
    cogs_path = cogs_spec.get('path') if isinstance(cogs_spec, Mapping) else []
    nodes = pl_nodes
    section: Mapping[str, object] = {}
    if isinstance(cogs_path, Sequence):
        for part in cogs_path:
            matches = [n for n in nodes if n.get('name') == part]
            if len(matches) != 1:
                raise ValueError('Missing or ambiguous COGS section: ' + str(part))
            section = matches[0]
            txs = section.get('account_transactions', [])
            nodes = [t for t in txs if isinstance(t, Mapping)] if isinstance(txs, Sequence) else []

    def cogs_leaves(nodes: Sequence[Mapping[str, object]]) -> Iterator[Mapping[str, object]]:
        for n in nodes:
            children = n.get('account_transactions')
            if children and isinstance(children, Sequence):
                child_maps = [c for c in children if isinstance(c, Mapping)]
                yield from cogs_leaves(child_maps)
            else:
                yield n
    leaves = list(cogs_leaves(nodes))
    if not abs(sum((D(str(n['total'])) for n in leaves), D(0)) - D(str(section['total']))) < D('.01'):
        raise ValueError('Financial arithmetic or report consistency check failed')
    for n in leaves:
        text.append(f"| {n['name']} | {f(D(str(n['total'])))} |")
    text.append(f'| **Books COGS section subtotal** | **{f(cogs)}** |')
    freight_spec = calculations.get('freight')
    freight_accounts = freight_spec.get('accounts') if isinstance(freight_spec, Mapping) else {}
    freight_map = freight_accounts if isinstance(freight_accounts, Mapping) else {}
    for name, coef in freight_map.items():
        text.append(f'| {name} — reclassified from operating expenses | {f(a[str(name)] * D(str(coef)))} |')
    text += [
        f'| **Books Total COGS compared with B15** | **{f(cogs + freight)}** |',
        f'| Audited Total COGS (B15) | {f(value(p, 15))} |',
        f'| **Difference — Books minus audited** | **{difference(cogs + freight - value(p, 15), debit_normal=True)}** |',
    ]
    text += [
        '', '### Trial balance — all account lines', '',
        'Source: [trial balance snapshot](trialbalance.json). Opening and closing balances retain Books Dr/Cr presentation. Trial balance does not establish gross purchases or an inventory roll-forward; those audited components require reviewed ledger mappings.',
        '', '| Account | Opening balance | Debits | Credits | Closing balance |',
        '|---|---:|---:|---:|---:|',
    ]

    def trial_lines(nodes: Sequence[object]) -> Iterator[Mapping[str, object]]:
        for node in nodes:
            if not isinstance(node, Mapping) or not isinstance(node.get('name'), str):
                raise ValueError('Invalid trial balance account row')
            children = node.get('accounts', node.get('account_transactions', []))
            child_seq = children if isinstance(children, Sequence) else []
            if node.get('account_id') or not children:
                yield node
            if children:
                yield from trial_lines(child_seq)

    def trial_amount(node: Mapping[str, object], field: str) -> str:
        values = node.get('values')
        if values is not None:
            if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], Mapping):
                raise ValueError('Invalid trial balance values')
            node = values[0]
        if field not in node:
            raise ValueError('Missing trial balance column: ' + field)
        amount = node.get(field + '_formatted', node[field])
        if isinstance(amount, (dict, list, bool)) or amount is None:
            raise ValueError('Invalid trial balance amount: ' + field)
        rendered = str(amount)
        return rendered.replace('|', '\\|').replace('\n', ' ')

    trial = reports['trialbalance'].get('trialbalance', [])
    for node in trial_lines([trial] if isinstance(trial, Mapping) else (trial if isinstance(trial, Sequence) else [])):
        label = str(node['name']).replace('|', '\\|').replace('\n', ' ')
        amounts = [trial_amount(node, field) for field in ('opening_balance', 'net_debit', 'net_credit', 'closing_balance')]
        text.append('| ' + ' | '.join([label, *amounts]) + ' |')
    for r in (11, 12, 14):
        text.append(f'| Audited {s[p][r - 1][0]} (B{r}) | — | — | — | {f(value(p, r))} |')
    text += [
        '',
        f"Books non-operating expenses total ₹{f(a['Non Operating Expense'])} (a negative value is a credit). This accounts for the difference between aligned operating profit less interest and Books net profit.",
        '',
        '## Balance-sheet comparison',
        '',
        '| Audited line / cell | Audited | Books | Difference | Mapping / qualification |',
        '|---|---:|---:|---:|---|',
    ]
    bm: dict[int, list[str]] = {
        int(k): [str(x) for x in v] if isinstance(v, Sequence) else []
        for k, v in balance_sheet_accounts.items()
    }
    pnl_balance_mapping: dict[int, list[str]] = {
        int(k): [str(x) for x in v] if isinstance(v, Sequence) else []
        for k, v in balance_sheet_pnl_accounts.items()
    }
    if pnl_balance_mapping.keys() - bm.keys():
        raise ValueError('P&L balance-sheet mappings require a balance_sheet_accounts row')
    for r, names in bm.items():
        if r == 26:
            continue  # GST payable uses the reviewed net calculation below.
        pnl_names = pnl_balance_mapping.get(r, [])
        note = ', '.join(names)
        if pnl_names:
            note += ' + ' + ', '.join(pnl_names) + ' (P&L; reviewed regrouping)'
        compared = total(b, names) + total(a, pnl_names)
        if r in (18, 28) and config.get('net_gst_in_balance_sheet_totals', False):
            compared -= gst_netting
            note += '; input GST netted against output GST liability'
        row(q, r, compared, note + ('; partner accounts only, excludes separate earnings' if r == 22 else ''))
    input_gst = total(b, ['Input CGST', 'Input IGST', 'Input SGST'])
    output_gst = total(b, ['Output CGST', 'Output IGST', 'Output SGST'])
    row(q, 26, output_gst - input_gst, 'Output GST minus Input GST (CGST, IGST and SGST)')
    for r in (9, 15):
        if r == 15 and config.get('audited_gst_asset_to_fixed_assets', False):
            text.append(f'| {s[q][r - 1][0]} (B15) | 0.00 | — | — | Audited source amount {f(value(q, 15))} regrouped into Fixed Assets B6 |')
            continue
        if r not in bm:
            text.append(f'| {s[q][r - 1][0]} (B{r}) | {f(value(q, r))} | — | — | Unmapped; ledger confirmation required |')
    text += [
        '',
        ('Sundry Debtors B9 uses the reviewed account mapping shown above.' if 9 in bm else 'Sundry Debtors B9 has no confirmed mapping; ledger confirmation required.'),
        f"GST Payable B26 uses Output GST minus Input GST: ₹{f(output_gst)} minus ₹{f(input_gst)} = ₹{f(output_gst - input_gst)}. Negative values represent net input credit. " + (f'Audited GST asset B15 ₹{f(value(q, 15))} is regrouped into Fixed Assets B6; audited total assets and GST payable are unchanged. ' if config.get('audited_gst_asset_to_fixed_assets', False) else f'Audited GST asset B15 ₹{f(value(q, 15))} remains separate; it is not deducted again from B26. ') + ('Compared assets and liabilities both exclude gross input GST; original Books snapshots remain unchanged.' if config.get('net_gst_in_balance_sheet_totals', False) else 'Books statement totals remain unchanged.'),
        f"Books retained earnings ₹{f(b['Retained Earnings'])} and current-year earnings ₹{f(b['Current Year Earnings'])} are presented separately from partner capital. Compare audited profit allocation before treating capital differences as errors.",
        '',
        '## Verification and follow-up',
        '',
        'The audited asset and liability line sums agree with their totals; the balance sheet balances. Audited income minus COGS, operating expenses and interest agrees with net profit. Books profit arithmetic also agrees.',
        'Reconcile receivable/payable schedules, partner profit allocation, depreciation and capitalisation, GST netting, and grouped operating expenses. Both source workbook and Books transactions were left unchanged.',
        '',
        '[Books P&L snapshot](profitandloss.json) · [Books balance sheet snapshot](balancesheet.json)',
        '',
    ]
    # Headline totals and residual expenses do not establish account-level matches.
    explicit_pnl = set(used)
    for name in ('sales', 'other_income', 'interest', 'freight'):
        spec_item = calculations.get(name)
        accounts_item = spec_item.get('accounts') if isinstance(spec_item, Mapping) else {}
        if isinstance(accounts_item, Mapping):
            explicit_pnl.update(str(k) for k in accounts_item.keys())
    for names in pnl_balance_mapping.values():
        explicit_pnl.update(names)
    explicit_bs = {name for r, names in bm.items() if r not in (18, 26, 28) for name in names}
    explicit_bs.update(['Input CGST', 'Input IGST', 'Input SGST', 'Output CGST', 'Output IGST', 'Output SGST'])
    unmatched: list[tuple[str, str, str, D, str, bool]] = []

    def find_unmatched(nodes: Sequence[Mapping[str, object]], report: str, mapped: set[str], covered: bool = False, path: tuple[str, ...] = ()) -> None:
        for node in nodes:
            name = str(node.get('name', ''))
            matched = covered or name in mapped or (report == 'P&L' and name == 'Cost of Goods Sold')
            children = node.get('account_transactions', [])
            child_maps = [c for c in children if isinstance(c, Mapping)] if isinstance(children, Sequence) else []
            if node.get('account_id') and not matched and D(str(node['total'])).quantize(D('.01')) != 0:
                reason = ('Excluded from audited operating expenses; mapping pending' if report == 'P&L' and name in excluded_expenses else 'Included only in Other Expenses residual; no explicit audited account match' if report == 'P&L' and 'Operating Expense' in path else 'No mapped audited line')
                debit_normal = ('Assets' in path) if report == 'Balance sheet' else any(
                    section in path for section in ('Operating Expense', 'Non Operating Expense', 'Cost of Goods Sold')
                )
                unmatched.append((report, name, str(node['account_id']), D(str(node['total'])), reason, debit_normal))
            find_unmatched(child_maps, report, mapped, matched, path + (name,))

    find_unmatched(pl_nodes, 'P&L', explicit_pnl)
    find_unmatched(bs_nodes, 'Balance sheet', explicit_bs)
    text += ['## Books accounts without an audited match', '',
             'Accounts covered by a mapped account group are matched. Statement totals alone do not count as matches. Zero balances at two-decimal precision are excluded. Amounts show absolute balances with Dr/Cr based on the statement section; negative balances reverse the normal side. These rows are not additive to the differences above.', '',
             '| Report | Account | Account ID | Books amount (INR) | Mapping gap |',
             '|---|---|---|---:|---|']
    for report, name, account_id, amount, reason, debit_normal in sorted(unmatched):
        text.append(f'| {report} | {name.replace("|", "&#124;")} | {account_id} | {difference(amount, debit_normal=debit_normal)} | {reason} |')
    if not unmatched:
        text.append('| — | No nonzero unmatched accounts in the fetched statement reports | — | — | — |')
    text.append('')
    return ComparisonResult('\n'.join(text), a['Net Profit/Loss'] - value(p, 39), compared_assets - value(q, 18))
