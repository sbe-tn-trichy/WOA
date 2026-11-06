---
type: Workflow
description: GSTIN-safe clearing of linked customer receivables and vendor payables through paired payments.
---

# Vendor-Customer Offset

The public workflow accepts the structural `OffsetBooksClient` protocol and
returns `OffsetReport`, with typed plans, posted/failed rows, summary counts,
allocations and dated Decimal tranches. Live calls require an explicit
`checkpoint_path` (normally beneath `output/vendor_customer_offset/`). The
checkpoint binds saved payment intent to the client's organization and domain.

`workflows.vendor_customer_offset.run_vendor_customer_offset()` offsets balances
for contacts that exist once as a customer and once as a vendor under the same
valid GSTIN. A GSTIN is skipped when either contact type occurs more than once.

The offset amount is the lower of the customer's outstanding receivable and the
vendor's outstanding payable. The workflow allocates the amount oldest-due-first
to open invoices and bills, and skips a pair rather than creating unapplied
credit when the open documents cannot absorb the complete amount.

The workflow creates one payment pair per participating vendor bill: one
customer payment and one vendor payment for the same amount and the bill's own
invoice date. When the available customer receivable is lower than total vendor
payables, the last participating bill is partially settled. Customer invoice
allocations carry forward across payment pairs without reusing an allocation.
A pair is skipped if a participating vendor bill has no valid date.
Generated references include the vendor bill ID and are capped at the live
Books limit of 50 characters.

Only documents with positive balances in payable/payment-eligible states are
allocated. Void, draft, paid, rejected, and approval-state invoices and bills
are excluded even if the list response retains a historical balance.

Both payments use the `Vendor To Customer` bank account by default. Customer
payments use `account_id`; vendor payments use `paid_through_account_id`.
Account ID can be supplied explicitly to avoid name lookup.
An optional `vendor_id` limits preview and posting to exactly one vendor.

Dry-run is enabled by default and does not verify or create the contact link.
During a live run, `ensure_linked=True` uses the Books web-client operation
`POST /customers/{customer_id}/link`; the Zoho `3051` response is treated as an
idempotent indication that the contacts are already linked.

The customer payment is created first. Before each create, the workflow atomically
saves both payloads, the requested stage, and any known IDs. Exceptions, missing
IDs and lost responses retain this evidence and stop further posting. Customer
payments are never automatically deleted: even a vendor rejection requires live
reconciliation before deciding whether compensation is appropriate.

Keep the checkpoint across reruns and machines. On a rerun, known IDs are read
back; missing IDs are searched using the saved reference/contact and then read
in detail. Both sides must uniquely match contact, clearing account, date,
reference, amount and allocations. Verified bill intents are skipped, preventing
duplicate creates. Absence, ambiguity, changed records, or failed reads stop the
run without retrying or deleting payments. Operators must reconcile unresolved
intent against Books; creating a new checkpoint is not a recovery procedure.

An exclusive sibling `.lock` prevents overlapping runs using the same checkpoint.
A process interruption leaves the lock: confirm the original process is stopped
and reconcile live state before removing it. Locks do not coordinate different
checkpoint paths; never run overlapping offsets for the same organization.
Checkpoint loss must be treated as lost recovery evidence, not proof that no
payments were posted. Dry runs create neither checkpoint nor lock. Unit tests
cover uncertain completion; no live financial mutations were used for validation.
