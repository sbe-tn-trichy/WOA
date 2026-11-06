import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from workflows.vendor_customer_offset import (
    VendorCustomerOffsetConfig,
    run_vendor_customer_offset,
)


GSTIN = "33ABCDE1234F1Z5"


def _contacts(customer_outstanding=120, vendor_outstanding=80):
    return [
        {
            "contact_id": "customer-1",
            "contact_type": "customer",
            "gst_no": GSTIN,
            "currency_code": "INR",
            "outstanding_receivable_amount": customer_outstanding,
        },
        {
            "contact_id": "vendor-1",
            "contact_type": "vendor",
            "gst_no": GSTIN,
            "currency_code": "INR",
            "outstanding_payable_amount": vendor_outstanding,
        },
    ]


class TestVendorCustomerOffset(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.checkpoint = Path(temporary.name) / "offset.json"
        self.books = MagicMock()
        self.books.organization_id = "org-1"
        self.books.domain = "in"
        self.books.bank_accounts.list_all.return_value = [
            {"account_id": "bank-1", "account_name": "Vendor To Customer"}
        ]
        self.books.contacts.list_all.return_value = _contacts()
        self.books.invoices.list_all.return_value = [
            {"invoice_id": "invoice-2", "due_date": "2026-02-01", "balance": 50},
            {"invoice_id": "invoice-1", "due_date": "2026-01-01", "balance": 50},
        ]
        self.books.bills.list_all.return_value = [
            {
                "bill_id": "bill-1",
                "date": "2026-01-10",
                "due_date": "2026-01-15",
                "balance": 50,
            },
            {
                "bill_id": "bill-2",
                "date": "2026-02-10",
                "due_date": "2026-02-15",
                "balance": 50,
            },
        ]

    def test_dry_run_uses_lowest_outstanding_and_allocates_oldest_first(self):
        result = run_vendor_customer_offset(self.books)

        self.assertEqual(result["summary"]["planned"], 2)
        self.assertEqual(result["summary"]["planned_customer_payments"], 2)
        self.assertEqual(result["summary"]["planned_vendor_payments"], 2)
        self.assertEqual([item["amount"] for item in result["planned"]], [50.0, 30.0])
        self.assertEqual(
            [item["payment_date"] for item in result["planned"]],
            ["2026-01-10", "2026-02-10"],
        )
        self.assertEqual(
            result["planned"][0]["invoice_allocations"],
            [{"invoice_id": "invoice-1", "amount_applied": 50.0}],
        )
        self.assertEqual(
            result["planned"][1]["invoice_allocations"],
            [{"invoice_id": "invoice-2", "amount_applied": 30.0}],
        )
        self.books.customer_payments.create.assert_not_called()
        self.books.vendor_payments.create.assert_not_called()
        self.books.request.assert_not_called()

    def test_live_run_verifies_link_and_posts_both_payments(self):
        self.books.request.side_effect = Exception(
            'HTTP Error: 400 - {"code":3051,"message":"already linked"}'
        )
        self.books.customer_payments.create.side_effect = [
            {"payment": {"payment_id": "cp-1"}},
            {"payment": {"payment_id": "cp-2"}},
        ]
        self.books.vendor_payments.create.side_effect = [
            {"vendorpayment": {"payment_id": "vp-1"}},
            {"vendorpayment": {"payment_id": "vp-2"}},
        ]

        result = run_vendor_customer_offset(
            self.books,
            VendorCustomerOffsetConfig(dry_run=False, checkpoint_path=self.checkpoint),
        )

        self.assertEqual(result["summary"]["posted"], 2)
        self.assertEqual(result["summary"]["posted_customer_payments"], 2)
        self.assertEqual(result["summary"]["posted_vendor_payments"], 2)
        self.assertEqual(result["posted"][0]["link_status"], "already_linked")
        customer_payloads = [
            call.args[0] for call in self.books.customer_payments.create.call_args_list
        ]
        vendor_payloads = [
            call.args[0] for call in self.books.vendor_payments.create.call_args_list
        ]
        self.assertEqual([item["amount"] for item in customer_payloads], [50.0, 30.0])
        self.assertEqual(
            [item["date"] for item in customer_payloads],
            ["2026-01-10", "2026-02-10"],
        )
        self.assertEqual(
            [item["date"] for item in vendor_payloads],
            ["2026-01-10", "2026-02-10"],
        )
        self.assertEqual(vendor_payloads[0]["bills"], [{"bill_id": "bill-1", "amount_applied": 50.0}])
        self.assertEqual(vendor_payloads[1]["bills"], [{"bill_id": "bill-2", "amount_applied": 30.0}])
        self.assertTrue(all(len(item["reference_number"]) <= 50 for item in customer_payloads))

    def test_duplicate_gstin_is_skipped(self):
        self.books.contacts.list_all.return_value = _contacts() + [
            {
                "contact_id": "customer-2",
                "contact_type": "customer",
                "gst_no": GSTIN,
                "currency_code": "INR",
                "outstanding_receivable_amount": 20,
            }
        ]

        result = run_vendor_customer_offset(self.books)

        self.assertEqual(result["candidate_pairs"], 0)
        self.assertEqual(result["skipped"][0]["reason"], "ambiguous_gstin")
        self.books.invoices.list_all.assert_not_called()

    def test_vendor_id_limits_the_run_to_one_vendor(self):
        result = run_vendor_customer_offset(
            self.books,
            VendorCustomerOffsetConfig(vendor_id="different-vendor"),
        )

        self.assertEqual(result["candidate_pairs"], 0)
        self.books.invoices.list_all.assert_not_called()

    def test_insufficient_documents_is_skipped(self):
        self.books.invoices.list_all.return_value = [
            {"invoice_id": "invoice-1", "balance": 70}
        ]

        result = run_vendor_customer_offset(self.books)

        self.assertEqual(result["skipped"][0]["reason"], "insufficient_open_documents")
        self.books.customer_payments.create.assert_not_called()

    def test_void_documents_are_not_allocated(self):
        self.books.invoices.list_all.return_value = [
            {"invoice_id": "void-invoice", "status": "void", "balance": 80},
            {"invoice_id": "open-invoice", "status": "overdue", "balance": 80},
        ]

        result = run_vendor_customer_offset(self.books)

        allocated_ids = {
            allocation["invoice_id"]
            for item in result["planned"]
            for allocation in item["invoice_allocations"]
        }
        self.assertEqual(allocated_ids, {"open-invoice"})

    def test_vendor_failure_retains_customer_payment_and_checkpoint(self):
        self.books.request.side_effect = Exception(
            'HTTP Error: 400 - {"code":3051,"message":"already linked"}'
        )
        self.books.customer_payments.create.return_value = {
            "payment": {"payment_id": "cp-1"}
        }
        self.books.vendor_payments.create.side_effect = RuntimeError("vendor failure")

        result = run_vendor_customer_offset(
            self.books,
            VendorCustomerOffsetConfig(dry_run=False, checkpoint_path=self.checkpoint),
        )

        self.books.customer_payments.delete.assert_not_called()
        self.assertIn("cp-1", self.checkpoint.read_text())
        with self.assertRaises((RuntimeError, ValueError)):
            run_vendor_customer_offset(self.books, VendorCustomerOffsetConfig(dry_run=False, checkpoint_path=self.checkpoint))
        self.assertEqual(result["failed"][0]["rollback"], "withheld_pending_live_reconciliation")

    def test_missing_vendor_invoice_date_is_skipped(self):
        self.books.bills.list_all.return_value = [
            {"bill_id": "bill-1", "balance": 80}
        ]

        result = run_vendor_customer_offset(self.books)

        self.assertEqual(result["skipped"][0]["reason"], "missing_vendor_invoice_date")
        self.books.customer_payments.create.assert_not_called()

class TestOffsetRecovery(unittest.TestCase):
    setUp = TestVendorCustomerOffset.setUp
    def _live_config(self):
        return VendorCustomerOffsetConfig(dry_run=False, ensure_linked=False,
                                          checkpoint_path=self.checkpoint)

    def test_live_requires_checkpoint_before_any_call(self):
        with self.assertRaisesRegex(RuntimeError, "checkpoint_path"):
            run_vendor_customer_offset(self.books, VendorCustomerOffsetConfig(dry_run=False))
        self.assertFalse(self.books.mock_calls)

    def test_committed_response_lost_is_reconciled_without_duplicate(self):
        customer_records, vendor_records = {}, {}

        def customer_create(payload):
            customer_records['cp-1'] = dict(payload, payment_id='cp-1')
            return {'payment': {'payment_id': 'cp-1'}}

        def vendor_create(payload):
            vendor_records['vp-1'] = dict(payload, payment_id='vp-1')
            raise TimeoutError('response lost')

        self.books.contacts.list_all.return_value = _contacts(50, 50)
        self.books.customer_payments.create.side_effect = customer_create
        self.books.vendor_payments.create.side_effect = vendor_create
        first = run_vendor_customer_offset(self.books, self._live_config())
        self.assertEqual(first['failed'][0]['customer_payment_id'], 'cp-1')
        self.books.customer_payments.delete.assert_not_called()
        self.books.customer_payments.get.side_effect = lambda key: {'payment': customer_records[key]}
        self.books.vendor_payments.list_all.return_value = list(vendor_records.values())
        self.books.vendor_payments.get.side_effect = lambda key: {'vendorpayment': vendor_records[key]}
        second = run_vendor_customer_offset(self.books, self._live_config())
        self.assertEqual(second['summary']['failed'], 0)
        self.assertEqual(self.books.customer_payments.create.call_count, 1)
        self.assertEqual(self.books.vendor_payments.create.call_count, 1)

    def test_missing_customer_id_keeps_intent_and_does_not_post_vendor(self):
        self.books.customer_payments.create.return_value = {'payment': {}}
        report = run_vendor_customer_offset(self.books, self._live_config())
        self.assertEqual(report['summary']['failed'], 1)
        self.books.vendor_payments.create.assert_not_called()
        self.assertIn('customer_create_requested', self.checkpoint.read_text())

    def test_missing_vendor_id_keeps_known_customer(self):
        self.books.customer_payments.create.return_value = {'payment': {'payment_id': 'cp-1'}}
        self.books.vendor_payments.create.return_value = {'vendorpayment': {}}
        report = run_vendor_customer_offset(self.books, self._live_config())
        self.assertEqual(report['failed'][0]['customer_payment_id'], 'cp-1')
        self.books.customer_payments.delete.assert_not_called()

    def test_stale_lock_blocks_before_network(self):
        self.checkpoint.with_suffix('.json.lock').touch()
        with self.assertRaisesRegex(RuntimeError, 'locked'):
            run_vendor_customer_offset(self.books, self._live_config())
        self.assertFalse(self.books.mock_calls)

    def test_checkpoint_scope_mismatch_blocks_before_network(self):
        import json
        self.checkpoint.write_text(json.dumps({'scope': {'organization_id': 'other', 'domain': 'in'}, 'operations': []}))
        with self.assertRaisesRegex(RuntimeError, 'organization/domain'):
            run_vendor_customer_offset(self.books, self._live_config())
        self.assertFalse(self.books.mock_calls)

    def test_checkpoint_write_failure_prevents_payment(self):
        from unittest.mock import patch
        with patch('workflows.vendor_customer_offset.processor.write_atomic_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                run_vendor_customer_offset(self.books, self._live_config())
        self.books.customer_payments.create.assert_not_called()

    def test_process_interruption_keeps_intent_and_blocks_replay(self):
        self.books.customer_payments.create.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            run_vendor_customer_offset(self.books, self._live_config())
        self.assertIn('customer_create_requested', self.checkpoint.read_text())
        self.books.customer_payments.list_all.return_value = []
        with self.assertRaisesRegex(RuntimeError, 'Existing offset intent'):
            run_vendor_customer_offset(self.books, self._live_config())
        self.assertEqual(self.books.customer_payments.create.call_count, 1)
        self.books.vendor_payments.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
