from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Dict, List, Mapping, NotRequired, Optional, Sequence, TypedDict

from workflows.core.matching import to_decimal
from zoho.validation import require_record, require_records, require_text


class StorageAllocation(TypedDict):
    storage_id: str
    out_quantity: float


class TransferPayload(TypedDict):
    date: str
    reference_number: str
    is_inclusive_tax: bool
    gst_treatment: str
    notes: str
    location_id: str
    tax_settings_id: str
    gst_no: str
    line_items: list[dict[str, object]]
    customer_id: NotRequired[str]
    place_of_supply: NotRequired[str]
    send: NotRequired[bool]
    vendor_id: NotRequired[str]
    is_draft: NotRequired[bool]
    bill_number: NotRequired[str]
    source_of_supply: NotRequired[str]
    destination_of_supply: NotRequired[str]


@dataclass(frozen=True)
class TransferLine:
    item_id: str
    sku: str
    name: str
    quantity: Decimal
    rate: Decimal
    source_stock: Decimal
    destination_stock: Decimal
    tax_id: str
    tax_percentage: Decimal
    sales_account_id: str
    inventory_account_id: str
    hsn_or_sac: str
    unit: str
    storages: list[StorageAllocation] = field(default_factory=list)


def number(value: object) -> Decimal:
    result = to_decimal(value)
    if result is None or not result.is_finite():
        raise ValueError('Missing or invalid numeric stock/rate')
    return result


def stocks(item: Mapping[str, object], source: str, destination: str) -> tuple[Decimal, Decimal, Decimal]:
    locations = {str(row['location_id']): row for row in require_records(item.get('locations'), 'Item locations')}
    s, d = locations[source], locations[destination]
    on_hand = number(s['location_stock_on_hand'])
    # Protect accounting stock, physical stock, and both commitment balances.
    cap = min(number(s[key]) for key in (
        'location_stock_on_hand', 'location_available_stock',
        'location_actual_available_stock', 'location_available_for_sale_stock',
        'location_actual_available_for_sale_stock',
    ))
    return on_hand, number(d['location_stock_on_hand']), max(Decimal(0), cap)


def build_plan(
    items: Sequence[Mapping[str, object]], source: str, destination: str,
    purchase_account_ids: Sequence[str], markup_percentage: Decimal = Decimal('1'),
) -> List[TransferLine]:
    """Match exact item IDs and cap shortage quantities at uncommitted source stock."""
    if not source or not destination or source == destination:
        raise ValueError('Two different locations are required')
    if not purchase_account_ids or markup_percentage < 0:
        raise ValueError('Explicit purchase accounts and nonnegative markup required')
    result = []
    seen = set()
    for item in items:
        item_id = str(item['item_id'])
        if item_id in seen:
            raise ValueError('Duplicate item ID')
        seen.add(item_id)
        if item.get('purchase_account_id') not in purchase_account_ids:
            raise ValueError('Item outside the scoped purchase accounts')
        if item.get('status') != 'active' or not item.get('track_inventory', item.get('item_type') == 'inventory'):
            continue
        source_stock, destination_stock, cap = stocks(item, source, destination)
        quantity = min(cap, max(Decimal(0), -destination_stock))
        if quantity <= 0:
            continue
        source_location = next(loc for loc in require_records(item.get('locations'), 'Item locations') if str(loc['location_id']) == source)
        allocations: list[StorageAllocation] = []
        if source_location.get('is_storage_location_enabled'):
            bins = require_records(item['transfer_bins'], 'Item transfer bins')
            if any(str(row['location_id']) != source for row in bins):
                raise ValueError('Bin belongs to another location')
            if len({row['storage_id'] for row in bins}) != len(bins):
                raise ValueError('Duplicate bin')
            eligible_bins = [row for row in bins if row.get('status') == 1 and number(row['balance_quantity']) > 0]
            quantity = min(quantity, sum((number(row['balance_quantity']) for row in eligible_bins), Decimal(0)))
            remaining = quantity
            for row in sorted(eligible_bins, key=lambda row: str(row['storage_id'])):
                take = min(remaining, number(row['balance_quantity']))
                if take > 0:
                    allocations.append(StorageAllocation(storage_id=require_text(row.get('storage_id'), 'Storage ID'), out_quantity=float(take)))
                    remaining -= take
            if quantity <= 0:
                continue
        if item.get('track_batch_number') or item.get('track_serial_number'):
            raise ValueError('Batch/serial tracked items require explicit allocations')
        cost = number(item['purchase_rate'])
        rate = (cost * (Decimal('1') + markup_percentage / Decimal('100'))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        taxes = [t for t in require_records(item.get('item_tax_preferences', []), 'Item tax preferences') if t.get('tax_specification') == 'intra']
        if cost <= 0 or rate <= 0 or len(taxes) != 1:
            raise ValueError('Positive rate and one intra-state item tax required')
        fields = ['account_id', 'inventory_account_id', 'hsn_or_sac', 'unit']
        if any(not item.get(key) for key in fields):
            raise ValueError('Missing accounting or item metadata')
        result.append(TransferLine(item_id, require_text(item.get('sku', ''), 'Item SKU', allow_empty=True), require_text(item.get('name'), 'Item name'), quantity, rate,
                                   source_stock, destination_stock, require_text(taxes[0].get('tax_id'), 'Item tax ID'),
                                   number(taxes[0]['tax_percentage']), require_text(item.get('account_id'), 'Sales account ID'),
                                   require_text(item.get('inventory_account_id'), 'Inventory account ID'), str(item['hsn_or_sac']), require_text(item.get('unit'), 'Item unit'), allocations))
    return result


def transaction_dates(starting_date: date, ending_date: date) -> List[date]:
    """Return the inclusive transaction dates, excluding Sundays."""
    if starting_date > ending_date:
        raise ValueError('starting_date must not be after ending_date')
    dates = []
    current = starting_date
    while current <= ending_date:
        if current.weekday() != 6:
            dates.append(current)
        current += timedelta(days=1)
    if not dates:
        raise ValueError('Date range contains no non-Sunday dates')
    return dates


def invoice_numbers(starting_number: str, prefix: str, count: int) -> List[str]:
    """Expand an explicit invoice number, preserving the numeric suffix width."""
    suffix = starting_number.removeprefix(prefix)
    if not prefix or not starting_number.startswith(prefix) or not re.fullmatch(r'[0-9]+', suffix):
        raise ValueError('Starting invoice number must match the prefix with a numeric suffix')
    if count < 0:
        raise ValueError('Invoice count must be nonnegative')
    return [f'{prefix}{int(suffix) + index:0{len(suffix)}d}' for index in range(count)]


def validate_series_start_date(
    starting_date: date, invoices: Sequence[Mapping[str, object]], invoice_number_prefix: str,
) -> Optional[date]:
    """Require a transfer start date on or after the latest invoice in a series."""
    if not invoice_number_prefix:
        raise ValueError('Explicit invoice number prefix required')
    series_dates = [
        date.fromisoformat(str(invoice['date']))
        for invoice in invoices
        if str(invoice.get('invoice_number', '')).startswith(invoice_number_prefix)
    ]
    latest = max(series_dates, default=None)
    if latest is not None and starting_date < latest:
        raise ValueError(
            f'Starting date {starting_date.isoformat()} is before latest invoice date '
            f'{latest.isoformat()} in series {invoice_number_prefix}'
        )
    return latest


def line_total(line: TransferLine, quantity: Optional[Decimal] = None) -> Decimal:
    """Estimate the final line total using Zoho's two-decimal tax rounding."""
    quantity = line.quantity if quantity is None else quantity
    subtotal = (quantity * line.rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    tax = (subtotal * line.tax_percentage / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    return subtotal + tax


def split_plan(lines: Sequence[TransferLine], maximum_invoice_total: Decimal) -> List[List[TransferLine]]:
    """Split quantities so every estimated invoice total stays within the cap."""
    limit = number(maximum_invoice_total).quantize(Decimal('0.01'))
    if limit <= 0:
        raise ValueError('maximum_invoice_total must be positive')
    documents: List[List[TransferLine]] = []
    current: List[TransferLine] = []
    current_total = Decimal('0')
    for original in lines:
        remaining = original.quantity
        while remaining > 0:
            unit_total = line_total(original, Decimal('1'))
            if unit_total > limit:
                raise ValueError(f'One unit of {original.sku} exceeds the invoice threshold')
            room = limit - current_total
            # Stock quantities in this workflow are discrete pieces.
            fit = min(remaining, (room / unit_total).to_integral_value(rounding='ROUND_FLOOR'))
            while fit > 0 and current_total + line_total(original, fit) > limit:
                fit -= 1
            if fit <= 0:
                documents.append(current)
                current, current_total = [], Decimal('0')
                continue
            storages: list[StorageAllocation] = []
            allocation_remaining = fit
            already_used = original.quantity - remaining
            skip = already_used
            for storage in original.storages:
                available = number(storage['out_quantity'])
                skipped = min(skip, available)
                skip -= skipped
                available -= skipped
                take = min(allocation_remaining, available)
                if take > 0:
                    storages.append(StorageAllocation(storage_id=storage['storage_id'], out_quantity=float(take)))
                    allocation_remaining -= take
            part = replace(original, quantity=fit, storages=storages)
            current.append(part)
            current_total += line_total(part)
            remaining -= fit
            if remaining > 0:
                documents.append(current)
                current, current_total = [], Decimal('0')
    if current:
        documents.append(current)
    return documents


def validate_stock(lines: Sequence[TransferLine], items: Sequence[Mapping[str, object]], source: str, destination: str) -> None:
    """Fail closed when a prepared quantity is no longer supported by live stock."""
    by_id = {str(i['item_id']): i for i in items}
    if len(by_id) != len(items):
        raise ValueError('Duplicate live items')
    for line in lines:
        _, shortage, cap = stocks(by_id[line.item_id], source, destination)
        if line.quantity <= 0 or line.quantity > cap or line.quantity > -shortage:
            raise ValueError(f'Stock changed or insufficient for {line.sku}; rebuild plan')
        if line.storages:
            bins = {row['storage_id']: row for row in require_records(by_id[line.item_id].get('transfer_bins'), 'Live transfer bins')}
            for allocation in line.storages:
                row = bins[allocation['storage_id']]
                if str(row['location_id']) != source or row.get('status') != 1 or number(row['balance_quantity']) < number(allocation['out_quantity']):
                    raise ValueError(f'Bin stock changed for {line.sku}')


def build_payloads(
    lines: Sequence[TransferLine], source: Mapping[str, object], destination: Mapping[str, object],
    customer: Mapping[str, object], vendor: Mapping[str, object], transaction_date: date, reference: str,
) -> dict[str, TransferPayload]:
    """Create matching draft payloads for two same-state GST registrations."""
    if not lines or not reference.strip():
        raise ValueError('Nonempty lines and reference required')
    if source['location_id'] == destination['location_id']:
        raise ValueError('Locations must differ')
    source_gstin = require_text(source.get('tax_reg_no'), 'Source GSTIN')
    destination_gstin = require_text(destination.get('tax_reg_no'), 'Destination GSTIN')
    if (not source.get('tax_reg_no') or not destination.get('tax_reg_no') or
        source['tax_reg_no'] == destination['tax_reg_no'] or
        source_gstin[:2] != destination_gstin[:2]):
        raise ValueError('This workflow requires distinct same-state GST registrations')
    for contact, location, kind in [(customer, destination, 'customer'), (vendor, source, 'vendor')]:
        if contact.get('gst_no') != location['tax_reg_no'] or contact.get('contact_type') != kind or contact.get('status') != 'active':
            raise ValueError(f'{kind} GSTIN/type/status does not match its location')
    result: dict[str, TransferPayload] = {}
    for kind, loc, contact in [('invoice', source, customer), ('bill', destination, vendor)]:
        location_id = require_text(loc.get('location_id'), 'Location ID')
        payload = TransferPayload(
            date=transaction_date.isoformat(), reference_number=reference,
            is_inclusive_tax=False, gst_treatment='business_gst',
            notes=f'Stock replenishment: {source["location_name"]} to {destination["location_name"]}. {reference}',
            location_id=location_id,
            tax_settings_id=require_text(loc.get('tax_settings_id'), 'Tax settings ID'),
            gst_no=require_text(contact.get('gst_no'), 'Contact GSTIN'), line_items=[],
        )
        for line in lines:
            payload['line_items'].append(dict(item_id=line.item_id, name=line.name, quantity=float(line.quantity),
                rate=float(line.rate), tax_id=line.tax_id, hsn_or_sac=line.hsn_or_sac, unit=line.unit,
                location_id=location_id, account_id=line.sales_account_id if kind == 'invoice' else line.inventory_account_id,
                description='Replenish negative destination stock; source stock capped'))
            if kind == 'invoice' and line.storages:
                payload['line_items'][-1]['storages'] = [dict(row) for row in line.storages]
        contact_id = require_text(contact.get('contact_id'), 'Contact ID')
        destination_address = require_record(destination.get('address'), 'Destination address')
        destination_state = require_text(destination_address.get('state_code'), 'Destination state')
        if kind == 'invoice':
            payload['customer_id'] = contact_id
            payload['place_of_supply'] = destination_state
            payload['send'] = False
        else:
            source_address = require_record(source.get('address'), 'Source address')
            payload['vendor_id'] = contact_id
            payload['is_draft'] = True
            payload['bill_number'] = reference
            payload['source_of_supply'] = require_text(source_address.get('state_code'), 'Source state')
            payload['destination_of_supply'] = destination_state
        result[kind] = payload
    return result
