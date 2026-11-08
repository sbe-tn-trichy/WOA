"""Typed data contracts for collection reconciliation and payment review."""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict, NotRequired, Required


class InvoiceAllocation(TypedDict, total=False):
    """Allocation of a customer payment to a specific invoice."""

    invoice_id: Required[str]
    invoice_number: str
    amount_applied: Required[float]
    balance: float
    due_date: str
    date: str


class ChequeDetail(TypedDict, total=False):
    """Normalized cheque record joined from Creator All_Cheque_Details."""

    record_id: str
    cheque_number: str
    customer_id: str
    presented_date: str
    amount: Decimal


class BankMatchCandidate(TypedDict, total=False):
    """Bank line retained for human inspection when matching is ambiguous."""

    transaction_id: str
    bank_name: str
    bank_account_id: str
    date: str
    amount: str
    reference: str
    description: str
    transaction_number: str
    suggested_customer_names: list[str]


class PaymentProposal(TypedDict, total=False):
    """Proposal uniting a Creator collection row with bank line & invoice preview."""

    id: str
    fingerprint: str
    payment_type: str
    creator: dict[str, object]
    bank: dict[str, object] | None
    bank_name: str
    bank_account_id: str
    ambiguous_candidates: list[BankMatchCandidate]
    possible_candidates: list[BankMatchCandidate]
    reviewable: bool
    reason: str
    decision: str
    push_status: str
    books_payment_id: str
    books_payment_number: str
    invoice_allocations: list[InvoiceAllocation]
    unallocated_amount: Decimal
    allocation_error: str
    error: str


class BankStatementRecord(BankMatchCandidate, total=False):
    """Uncategorized Books source line and IDs of competing Creator proposals."""

    kind: str
    customer_suggestions: list[str]
    expense_account_name: str
    transfer_account_name: str
    vendor_name: str
    location_name: str
    categorization_status: str
    creator_entry_ids: list[str]
    transfer_ids: list[str]
    recovery_checkpoint: bool


class BankTransferProposal(TypedDict):
    """One withdrawal/deposit pair and its durable Books posting checkpoint."""

    id: str
    source: dict[str, str]
    destination: dict[str, str]
    match_status: str
    status: str
    transfer_id: str
    error: str
    completed_at: NotRequired[str]
