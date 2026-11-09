"""Nominal identifiers for validated records; these do not validate tenant scope."""

from typing import NewType

PaymentId = NewType("PaymentId", str)
InvoiceId = NewType("InvoiceId", str)
CustomerId = NewType("CustomerId", str)
AccountId = NewType("AccountId", str)
LocationId = NewType("LocationId", str)
PurchaseAccountId = NewType("PurchaseAccountId", str)
OrganizationId = NewType("OrganizationId", str)

__all__ = [
    "PaymentId",
    "InvoiceId",
    "CustomerId",
    "AccountId",
    "LocationId",
    "PurchaseAccountId",
    "OrganizationId",
]
