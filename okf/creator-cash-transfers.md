---
type: Runbook
title: Creator Cash Transfer Posting
description: Explicit API posting of selected Creator cash payments and their associated Books deposit.
---

# Creator cash transfers

`workflows.creator_payments.cash_transfers.post_cash_transfer` handles one explicitly
selected Creator `Cash_Transfer` record. Its primary command is
`apps/payments/post_creator_cash_transfer.py`. It runs on demand in WOA, without
installing a Deluge function, automatic trigger or schedule inside Creator.

```sh
.venv/bin/python apps/payments/post_creator_cash_transfer.py --transfer-id CREATOR_ID --location-id BOOKS_LOCATION_ID
# Add --apply only for explicitly authorized live posting.
```

The Books location is mandatory; deployment defaults are not guessed. Creator
`Account_Details.Account_ID` supplies both account mappings. The source must be
the active Books Undeposited Funds account, and both accounts must use INR.
Only one destination is supported. All linked payments must be cash, point back
to the transfer and source account, and have dates no later than the deposit.
Their full amounts, the transfer amount, total and any supplied destination-row
amount must agree. Partially transferred or already settled payments require
reconciliation if no associated deposit is found. Explicitly exposed invoice or
discount instructions are rejected for separate review.

The workflow creates missing customer payments into Undeposited Funds with the
selected location, Creator identifiers and original date. Creator `Reference`
is the cash **Receipt Number** (`cf_receipt_number`) in Books; it does not populate
payment `reference_number`. Existing payments must have the matching Receipt
Number; unrelated Reference # values are preserved. It leaves
only excess credit unapplied when scoped outstanding invoices are insufficient.
Books generates payment numbers. Existing native IDs, Creator marker matches and unique date/amount/
receipt/customer candidates are checked against live detail before reuse;
ambiguous or conflicting links abort before financial writes.
Same-date/amount candidates are read in detail when lists omit custom fields.
Legacy matches using Reference # are also detected to prevent duplication, but
require a verified Receipt Number correction before reuse.

## Oldest outstanding invoice first

Payments apply to the same customer's outstanding invoices in the selected Books
location, ordered by **invoice date**, then due date and numeric invoice ID for
ties. This differs from the collection review's existing due-date-first rule.
The Books list's location filter is also enforced locally because the live API
can return other locations' historical invoices. Missing scope fields are fetched
from invoice detail; malformed balances, dates and customer identities fail.
Draft, void, paid and other closed/unapproved documents are excluded.

New payments carry their planned invoice applications at creation. Existing
payments keep all current applications and allocate only their unused credit.
Payments for a shared customer reserve invoice balances in payment-date/Creator-ID
order, avoiding overlapping plans against the same balance. Withholding or
discount applications require separate review. If invoice balances are
insufficient, the result's `unused_amounts` explicitly reports remaining credit.

The dry run records `allocation_preview` in the checkpoint, including invoice
numbers, dates, planned additional amounts and before/after unused credit.
Balances and payment applications are checked again immediately before mutation.
Allocation-only updates send just the complete invoice application array,
preserving financial identity and existing applications. Both payment applications
and affected invoice balances are read back; an existing deposit is reverified
afterward. No payment or deposit is recreated to allocate unused credit.

After all payments pass live read-back, the workflow creates one `deposit` bank
transaction whose line items reference the selected Books payment IDs.
The request includes header `from_account_id` for account-type validation and
omits header `amount`: supplying the amount makes Books add a separate
unassociated line in addition to the payment lines. Omitting the source account
on creation causes Books error 11016 even with valid source accounts on lines.
The associated line amounts supply the complete deposit total. Read-back
must confirm exact date, accounts, location, amount and payment associations.
A same-day equal-amount or transfer-reference deposit candidate is validated
instead of blindly duplicated. Creator payment Books IDs/numbers are saved after
payment verification; cash statuses become `Settled`, balances become zero, and
the transfer receives the deposit ID and `Verified` status only after the deposit
is verified. Creator updates skip workflows to prevent recursive posting. They do
not advance a Creator blueprint stage.

When a transfer becomes Verified, Creator removes it from the Pending report.
Read-back falls back to the `Verified` report only for no-record responses.
That report omits the destination subform. A later completed-run reconciliation
therefore requires its original, scope-matched checkpoint: visible transfer
identity, date, source, payment links and totals must still match; the approved
destination mapping and complete associated Books deposit are revalidated.
Without that checkpoint, a verified transfer with a hidden destination stops
for review rather than guessing a destination.

# Recovery and limits

Atomic checkpoints default to `output/cash_transfer/transfer_ID.json`. They include
the organization, Creator owner/app, location, approved financial signature,
source snapshot, attempted payloads, confirmed native IDs and operation states.
`UNKNOWN` is saved before each financial create. A lost response is reconciled
through fresh native evidence; when no matching native record can be established,
the workflow stops rather than replaying the uncertain write. A known returned
ID remains recorded even when subsequent verification fails. Fix conflicts only
after inspecting both services; no automatic rollback is performed.

The checkpoint-directory lock serializes local cash-posting runs. Keep it and the
checkpoint on the executing machine; do not run overlapping financial jobs from
other machines or checkpoint directories. Reconcile live state before removing
a stale lock or transferring recovery state. A successful Books post followed by
a Creator update failure leaves financial records intact for verified reuse.

Allocation updates also save an `UNKNOWN` operation before the request, including
the native payment ID, previous payment snapshot, complete desired applications
and expected unused credit. A lost response can be reconciled only when fresh
payment applications and unused credit exactly match that desired state;
otherwise execution stops for inspection. A verified rerun preserves applications
and performs no additional allocation write when no credit remains.

The public result reports `PREVIEW` or `COMPLETE`, checkpoint location, payment
IDs and deposit ID. Remote errors/read-back failures are failures, even when a
partial financial write succeeded. Tests mock both services; actual verification
and platform limits belong in the project changelog.

See [Books bank transactions](https://www.zoho.com/books/api/v3/bank-transactions/),
[deposit operations](https://www.zoho.com/in/books/help/banking/deposits.html) and
[configuration](configuration.md).
