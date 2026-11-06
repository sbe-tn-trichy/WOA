"""Typed resource contracts and wire-compatible offset reports."""

from datetime import date
from decimal import Decimal
from typing import NotRequired, Protocol, TypedDict


class ListResource(Protocol):
    def list_all(self, params: dict[str, object] | None = None, resource_key: str | None = None) -> object: ...


class PaymentResource(Protocol):
    def list_all(self, params: dict[str, object] | None = None, resource_key: str | None = None) -> object: ...
    def get(self, resource_id: str) -> object: ...
    def create(self, data: dict[str, object]) -> object: ...
    def delete(self, resource_id: str) -> object: ...


class OffsetBooksClient(Protocol):
    @property
    def organization_id(self) -> str: ...
    @property
    def domain(self) -> str: ...
    @property
    def contacts(self) -> ListResource: ...
    @property
    def bank_accounts(self) -> ListResource: ...
    @property
    def invoices(self) -> ListResource: ...
    @property
    def bills(self) -> ListResource: ...
    @property
    def customer_payments(self) -> PaymentResource: ...
    @property
    def vendor_payments(self) -> PaymentResource: ...
    def request(self, method: str, endpoint: str, *, data: dict[str, object]) -> object: ...


class InvoiceAllocation(TypedDict):
    invoice_id: str
    amount_applied: float


class BillAllocation(TypedDict):
    bill_id: str
    amount_applied: float


class OffsetTranche(TypedDict):
    amount: Decimal
    payment_date: date
    invoice_allocations: list[InvoiceAllocation]
    bill_allocations: list[BillAllocation]


class PairSummary(TypedDict):
    gstin: str
    customer_id: str
    vendor_id: str
    amount: float


class AmbiguousPair(TypedDict):
    gstin: str
    reason: str
    customer_count: int
    vendor_count: int


class SkippedOffset(PairSummary):
    reason: str
    unallocated_amount: NotRequired[float]


class PlannedOffset(PairSummary):
    payment_date: str
    invoice_allocations: list[InvoiceAllocation]
    bill_allocations: list[BillAllocation]
    link_status: str


class PostedOffset(PairSummary):
    bill_id: str
    payment_date: str
    customer_payment_id: str
    vendor_payment_id: str
    link_status: str


class FailedOffset(PairSummary):
    customer_payment_id: NotRequired[str]
    vendor_payment_id: NotRequired[str]
    error: str
    rollback: str
    bill_id: NotRequired[str]
    payment_date: NotRequired[str]


class OffsetSummary(TypedDict):
    planned: int
    posted: int
    planned_customer_payments: int
    planned_vendor_payments: int
    posted_customer_payments: int
    posted_vendor_payments: int
    skipped: int
    failed: int


class OffsetReport(TypedDict):
    dry_run: bool
    bank_account_id: str
    candidate_pairs: int
    planned: list[PlannedOffset]
    posted: list[PostedOffset]
    skipped: list[AmbiguousPair | SkippedOffset]
    failed: list[FailedOffset]
    summary: OffsetSummary
