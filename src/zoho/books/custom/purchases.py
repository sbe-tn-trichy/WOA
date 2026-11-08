from collections import defaultdict
from collections.abc import Iterable
from typing import Any
from ..base import BaseResource
from .mixins import StatusMixin, ApprovalMixin, CreditsMixin

class Bills(BaseResource, StatusMixin, ApprovalMixin, CreditsMixin):
    # Top-level requirements
    required_fields = ["bill_number", "vendor_id", "date", "line_items"]
    
    # Top-level defaults
    defaults = {
        "adjustment": 0,
        "adjustment_description": "Adjustment",
        "is_item_level_tax_calc": False,
        "is_draft": True,
        "discount": 0,
        "discount_type": "entity_level",
        "gst_treatment": "business_gst",
        "entity_type": "bill"
    }

    # Line item requirements
    line_item_required_fields = [
        "item_id", "account_id", "rate", "quantity", 
        "tax_id", "name", "hsn_or_sac"
    ]

    # Line item defaults
    line_item_defaults = {
        "discount": 0,
        "itc_eligibility": "eligible",
        "unit": "NOS"
    }

    def __init__(self, client: Any):
        super().__init__(client, 'bills')

    @staticmethod
    def normalize_bill_number(bill_number: Any) -> str:
        """Normalize bill numbers for duplicate grouping."""
        if bill_number is None:
            return ""
        return str(bill_number).strip()

    @classmethod
    def find_duplicate_groups(cls, bills: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Group bill records with repeated non-blank bill numbers."""
        groups = defaultdict(list)

        for bill in bills:
            bill_number = cls.normalize_bill_number(bill.get("bill_number"))
            if bill_number:
                groups[bill_number].append(bill)

        return {
            bill_number: bill_group
            for bill_number, bill_group in groups.items()
            if len(bill_group) > 1
        }

    def list_duplicate_bill_groups(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch all bills and return groups with duplicate bill numbers."""
        bills = self.list_all(resource_key="bills")
        return self.find_duplicate_groups(bills)



    def add_attachment(self, bill_id: str, file_content: Any, filename: str) -> dict[str, Any]:
        """
        Attach a file to an existing bill.
        """
        files = {
            'attachment': (filename, file_content)
        }
        return self.client.request('POST', f"{self.endpoint}/{bill_id}/attachment", files=files)

class PurchaseOrders(BaseResource, StatusMixin):
    def __init__(self, client: Any):
        super().__init__(client, 'purchaseorders')

    def mark_as_billed(self, po_id: str) -> dict[str, Any]:
        return self._action('POST', po_id, 'status/billed')

    def mark_as_cancelled(self, po_id: str) -> dict[str, Any]:
        return self._action('POST', po_id, 'status/cancelled')

class VendorPayments(BaseResource):
    def __init__(self, client: Any):
        super().__init__(client, 'vendorpayments')

    def update_with_number_series(self, payment_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update location and chosen payment number without auto numbering."""
        from utils.file_utils import json

        if not payment_id or not data.get("location_id"):
            raise ValueError("Payment ID and destination location are required")
        if not data.get("payment_number_prefix") or not data.get("payment_number_suffix"):
            raise ValueError("Payment number prefix and suffix are required")
        return self.update(
            payment_id, {},
            files={"JSONString": (None, json.dumps(data)),
                   "ignore_auto_number_generation": (None, "true")},
        )


class Expenses(BaseResource):
    """Zoho Books expenses resource."""

    def __init__(self, client: Any):
        super().__init__(client, 'expenses')
