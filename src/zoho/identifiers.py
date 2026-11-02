"""Nominal identifiers for validated records; these do not validate tenant scope."""

from typing import NewType

PaymentId = NewType("PaymentId", str)
InvoiceId = NewType("InvoiceId", str)
CustomerId = NewType("CustomerId", str)
AccountId = NewType("AccountId", str)
LocationId = NewType("LocationId", str)

__all__ = ["PaymentId", "InvoiceId", "CustomerId", "AccountId", "LocationId"]
