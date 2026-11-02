"""Minimal structural contracts, compatible with the existing SDK resources."""

from typing import Protocol


class PaymentResource(Protocol):
    def get(self, resource_id: str) -> object: ...
    def list_all(self) -> object: ...
    def update_with_number_series(self, payment_id: str, data: dict[str, str]) -> object: ...


class RenumberBooksClient(Protocol):
    @property
    def customer_payments(self) -> PaymentResource: ...


class DiscoveryQueries(Protocol):
    def execute(
        self, workspace_id: str, sql_query: str, *, max_attempts: int,
        poll_interval: float,
    ) -> object: ...


class RenumberAnalyticsClient(Protocol):
    @property
    def queries(self) -> DiscoveryQueries: ...
