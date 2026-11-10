"""Read-only hints for uncategorized Books bank statement lines."""

from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from ..core.matching import get_bank_reference, parse_date, to_decimal, to_text
from workflows.collection_payments.types import BankStatementRecord, BankTransferProposal
from workflows.runtime.exceptions import ReconciliationError


_SPACES = re.compile(r"[^a-z0-9]+")
_REDACTED_VPA = re.compile(r"^x{2,}(.{4})$", re.IGNORECASE)
_TA_SUFFIX = re.compile(r"(?:^|/)TA\s*$", re.IGNORECASE)
_CHEQUE_CLEARING_NARRATION = re.compile(
    r"\bCHQ\s+DEP\s*-\s*CTS\s+CLG1\b[^:]*", re.IGNORECASE
)


def _customer_narration(value: Any) -> str:
    return _CHEQUE_CLEARING_NARRATION.sub("", to_text(value)).strip(" -/: ")

GENERIC_NARRATION_TOKENS = {
    "upi", "cr", "dr", "no remark", "payment from ph", "sent using payt",
    "payment", "fund transfer", "bill", "urgent", "ta", "salary",
    "imps", "neft", "rtgs", "chq dep", "cts clg", "cts clg1", "by transfer",
    "transfer", "credit", "debit", "auto sweep", "sweep", "sweepout", "funds insufficient",
    "chq dep ret", "neft cr", "neft dr", "inward", "outward", "interest", "charges",
}

GENERIC_BANKS = {
    "state bank of i", "state bank of india", "indian bank", "indian overseas",
    "canara bank", "hdfc bank ltd", "hdfc", "icici", "union bank of i",
    "karur vysa bank", "city union bank", "axis bank", "bank of india",
    "idfc", "idfc first bank", "idfc bank", "idfc fir", "kotak", "kotak mahindra",
    "sbi", "sbin", "ioba", "ubin", "idib", "ciub", "hdfcbank", "okaxis",
    "okhdfcbank", "oksbi", "okicici", "ybl", "ibl", "axl", "ptyes", "ptsbi",
}


def extract_remitter_tokens(description: Any) -> list[str]:
    """Extract distinct search tokens (UPI VPA, phone, remitter name) from bank narration."""
    text = _customer_narration(description)
    if not text:
        return []
    tokens: set[str] = set()

    # 1. 10-digit mobile numbers
    for m in re.finditer(r"\b[6-9]\d{9}\b", text):
        tokens.add(m.group(0))

    # 2. VPA handles (e.g. user@bank, user@okaxis)
    for m in re.finditer(r"[a-zA-Z0-9._]{3,}@[a-zA-Z0-9]+", text):
        vpa = m.group(0)
        prefix, handle = vpa.split("@")
        redacted = _REDACTED_VPA.fullmatch(prefix)
        if redacted:
            # Keep the handle: four visible characters alone are not an identity.
            suffix = redacted.group(1)
            if not re.fullmatch(r"x+", suffix, re.IGNORECASE):
                tokens.add(f"{suffix}@{handle}")
            continue
        tokens.add(vpa)
        if len(prefix) >= 5 and not re.match(r"^x+$", prefix, re.IGNORECASE):
            tokens.add(prefix)

    # 3. Delimited segments
    for seg in re.split(r"[/:\-]", text):
        s = seg.strip(" -/:._")
        s_lower = s.lower()
        if (
            "@" not in s  # VPA tokens are handled above, including redaction
            and len(s) >= 4
            and s_lower not in GENERIC_NARRATION_TOKENS
            and s_lower not in GENERIC_BANKS
            and not (s.isdigit() and len(s) != 10)  # non-phone numbers (amounts, cheques, years)
            and not re.match(r"^\d{10,}$", s)  # reference number or phone already handled
            and not re.match(r"^x+\d*$", s, re.IGNORECASE)  # masked account xxxxx6216
            and not re.match(r"^[a-zA-Z]{4}0[0-9a-zA-Z]{6}$", s)  # IFSC code
            and not re.match(r"^[a-zA-Z0-9]{12,}$", s)  # bank hashes / UTRs without spaces
            and not any(sw in s_lower for sw in ("sweep", "fd 10", "charge", "interest"))
        ):
            tokens.add(s)

    return sorted(tokens, key=lambda x: (-len(x), x))


def _words(value: Any) -> str:
    return " ".join(_SPACES.sub(" ", to_text(value).casefold()).split())


def is_travel_allowance_withdrawal(transaction: Mapping[str, Any]) -> bool:
    direction = to_text(transaction.get("debit_or_credit") or transaction.get("transaction_type")).casefold()
    return direction in {"credit", "withdrawal", "expense"} and bool(
        _TA_SUFFIX.search(to_text(transaction.get("description") or transaction.get("narration")))
    )


class CustomerFinderIndex:
    """Index Finder names and narrations once for a bank statement refresh."""

    def __init__(self, finder_rows: Sequence[Mapping[str, Any]]) -> None:
        self.aliases: dict[str, set[str]] = {}
        self.descriptions: dict[str, set[str]] = {}
        self.upi_suffixes: dict[str, set[str]] = {}
        for row in finder_rows:
            if not isinstance(row, Mapping):
                continue
            name = to_text(row.get("Customer Name"))
            normalized = _words(name)
            if not normalized:
                continue
            for alias in {normalized, _words(name.split(" - ", 1)[0])}:
                if len(alias) >= 8 and len(alias.split()) >= 2:
                    self.aliases.setdefault(alias, set()).add(name)
            for vpa in re.findall(r"[a-zA-Z0-9._]{3,}@[a-zA-Z0-9]+", to_text(row.get("Description"))):
                local, handle = vpa.casefold().split("@")
                if len(local) >= 4 and local[-4:] != "xxxx":
                    self.upi_suffixes.setdefault(f"{local[-4:]}@{handle}", set()).add(name)
            description = _words(_customer_narration(row.get("Description")))
            if len(description) >= 12:
                self.descriptions.setdefault(description, set()).add(name)

    def suggest(self, transaction: Mapping[str, Any]) -> list[str]:
        raw_description = _customer_narration(transaction.get("description") or transaction.get("narration"))
        description = _words(raw_description)
        if not description:
            return []
        names = set(self.descriptions.get(description, ()))
        for vpa in re.findall(r"[a-zA-Z0-9._]{3,}@[a-zA-Z0-9]+", raw_description):
            local, handle = vpa.casefold().split("@")
            if _REDACTED_VPA.fullmatch(local) and local[-4:] != "xxxx":
                names.update(self.upi_suffixes.get(f"{local[-4:]}@{handle}", ()))
        padded = f" {description} "
        for alias, matching_names in self.aliases.items():
            if f" {alias} " in padded:
                names.update(matching_names)
        return sorted(names, key=str.casefold)


def customer_name_suggestions(
    transaction: Mapping[str, Any], finder_rows: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Find customer names from matching Finder names or descriptions."""
    return CustomerFinderIndex(finder_rows).suggest(transaction)


def bank_line_kind(transaction: Mapping[str, Any]) -> str:
    kind = to_text(transaction.get("debit_or_credit") or transaction.get("transaction_type")).casefold()
    narration = _words(transaction.get("description") or transaction.get("narration"))
    if kind in {"credit", "withdrawal", "expense"} and re.search(
        r"(?<![a-z0-9])poly2300277498(?![a-z0-9])",
        to_text(transaction.get("description") or transaction.get("narration")).casefold(),
    ):
        return "vendor_advance"
    if kind in {"debit", "deposit", "income"} and " cash deposit " in f" {narration} ":
        return "cash_deposit"
    if kind in {"credit", "withdrawal", "expense"} and "tnpdcl" in to_text(transaction.get("description") or transaction.get("narration")).casefold():
        return "electricity"
    if kind in {"credit", "withdrawal", "expense"} and " salary " in f" {narration} ":
        return "salary"
    if is_travel_allowance_withdrawal(transaction):
        return "travel_allowance"
    if kind in {"debit", "deposit", "income"}:
        return "deposit"
    if kind in {"credit", "withdrawal", "expense"}:
        return "withdrawal"
    return "other"


def suggest_names_for_tokens(
    tokens: Sequence[str],
    historical_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Return sorted customer names from ``historical_rows`` matching any token."""
    if not tokens or not historical_rows:
        return []
    tokens_lower = [t.casefold() for t in tokens if t]
    names = {
        to_text(row.get("Customer Name")).strip()
        for row in historical_rows
        if isinstance(row, Mapping)
        and to_text(row.get("Customer Name"))
        and any(t in to_text(row.get("Description")).casefold() for t in tokens_lower)
    }
    return sorted((n for n in names if n), key=str.casefold)


def check_customer_name(
    entry: MutableMapping[str, Any],
    historical_rows: Sequence[Mapping[str, Any]],
    *,
    customer_finder_view_id: str,
) -> None:
    """Verify Creator customer name against historical Analytics remitter records."""
    if not customer_finder_view_id or not entry.get("bank"):
        return

    bank_desc = entry["bank"].get("description")
    tokens = extract_remitter_tokens(bank_desc)
    if not tokens:
        entry["customer_name_valid"] = None
        entry["customer_name_reason"] = "No remitter identifiers in bank narration for Analytics lookup."
        entry["historical_customer_names"] = []
        return

    tokens_lower = [t.casefold() for t in tokens if t]
    matching_rows = [
        row
        for row in historical_rows
        if isinstance(row, Mapping)
        and to_text(row.get("Customer Name"))
        and any(t in to_text(row.get("Description")).casefold() for t in tokens_lower)
    ]

    if not matching_rows:
        entry["customer_name_valid"] = None
        entry["customer_name_reason"] = "No historical customer match found in Analytics."
        entry["historical_customer_names"] = []
        return

    historical_names = sorted(
        {
            to_text(row.get("Customer Name")).strip()
            for row in matching_rows
            if to_text(row.get("Customer Name")).strip()
        },
        key=str.casefold,
    )
    entry["historical_customer_names"] = historical_names

    if len(historical_names) > 1:
        entry["customer_name_valid"] = None
        entry["customer_name_reason"] = (
            "Note: Analytics history matches multiple customers; "
            "customer identity is inconclusive. Review may proceed. Matches: "
            + ", ".join(historical_names)
        )
        return

    expected = " ".join(to_text(entry["creator"].get("customer_name")).split()).casefold()

    def _matches_expected(name: str) -> bool:
        clean_name = " ".join(name.split()).casefold()
        return (
            clean_name == expected
            or expected.startswith(clean_name + " ")
            or clean_name.startswith(expected + " ")
            or clean_name.split(" - ")[0] == expected.split(" - ")[0]
        )

    if any(_matches_expected(n) for n in historical_names):
        entry["customer_name_valid"] = True
        entry["customer_name_reason"] = "Customer name confirmed by Analytics history."
    else:
        other_names = ", ".join(historical_names)
        entry["customer_name_valid"] = False
        entry["customer_name_reason"] = (
            f"Conflict: Analytics historical records for this remitter belong to "
            f"'{other_names}', not '{entry['creator'].get('customer_name')}'."
        )


def display_bank_transaction(transaction: Mapping[str, Any]) -> dict[str, Any]:
    """Shape a Books bank line into its review-queue display dictionary."""
    account_id = to_text(transaction.get("_review_bank_account_id"))
    return {
        "transaction_id": to_text(transaction.get("transaction_id") or transaction.get("id")),
        "transaction_number": to_text(transaction.get("transaction_number") or transaction.get("transaction_no")),
        "date": to_text(transaction.get("date") or transaction.get("transaction_date")),
        "amount": to_text(transaction.get("amount")),
        "reference": to_text(get_bank_reference(transaction, account_id)),
        "description": to_text(transaction.get("description") or transaction.get("narration")),
    }


def build_bank_statement_views(
    bank_transactions: Sequence[Mapping[str, Any]],
    bank_comparisons: Sequence[Mapping[str, Any]],
    bank_transfers: Sequence[BankTransferProposal],
    transfer_lines: Mapping[tuple[str, str], list[BankTransferProposal]],
    previous: Mapping[str, Any],
    customer_finder: CustomerFinderIndex,
    used_transaction_ids: set[str],
    *,
    travel_expense_account_name: str,
    cash_account_name: str,
    vendor_advance_vendor_name: str,
    vendor_advance_location_name: str,
) -> tuple[list[dict[str, Any]], list[BankStatementRecord]]:
    """Build ``bank_suggestions`` and ``bank_records`` for a refreshed review batch."""
    previous_bank = {to_text(row.get("transaction_id")): row for row in previous.get("bank_suggestions", [])}
    creator_claims: dict[tuple[str, str], list[str]] = {}
    for comparison in bank_comparisons:
        candidates = (
            [{**comparison["bank"], "bank_account_id": comparison["bank_account_id"]}]
            if comparison.get("bank")
            else []
        )
        candidates += comparison["ambiguous_candidates"] + comparison["possible_candidates"]
        for key in {(cand.get("bank_account_id", ""), cand["transaction_id"]) for cand in candidates}:
            creator_claims.setdefault(key, []).append(comparison["id"])

    non_customer_kinds = {"travel_allowance", "electricity", "salary", "cash_deposit", "vendor_advance"}
    bank_suggestions: list[dict[str, Any]] = []
    bank_records: list[BankStatementRecord] = []
    for transaction in bank_transactions:
        transaction_id = to_text(transaction.get("transaction_id") or transaction.get("id"))
        if not transaction_id:
            continue
        kind = bank_line_kind(transaction)
        account_id = to_text(transaction.get("_review_bank_account_id"))
        displayed = {
            **display_bank_transaction(transaction),
            "bank_name": to_text(transaction.get("_review_bank_name")),
            "bank_account_id": account_id,
            "kind": kind,
            "customer_suggestions": customer_finder.suggest(transaction) if kind not in non_customer_kinds else [],
            "expense_account_name": (
                travel_expense_account_name if kind == "travel_allowance"
                else "Electricity" if kind == "electricity"
                else "Salary" if kind == "salary" else ""
            ),
            "transfer_account_name": cash_account_name if kind == "cash_deposit" else "",
            "vendor_name": vendor_advance_vendor_name if kind == "vendor_advance" else "",
            "location_name": vendor_advance_location_name if kind == "vendor_advance" else "",
            "categorization_status": "pending",
        }
        identity = (account_id, transaction_id)
        if identity in transfer_lines:
            pairs = transfer_lines[identity]
            if all(pair["status"] == "completed" for pair in pairs):
                continue
            displayed.update(kind="bank_transfer", customer_suggestions=[], transfer_ids=[pair["id"] for pair in pairs])
        if previous_bank.get(transaction_id, {}).get("categorization_status") == "categorized":
            continue
        creator_candidates = creator_claims.get((account_id, transaction_id), [])
        bank_records.append({**displayed, "creator_entry_ids": creator_candidates})  # type: ignore[typeddict-item]
        if transaction_id not in used_transaction_ids:
            bank_suggestions.append(displayed)

    visible_ids = {
        (to_text(row.get("bank_account_id")), to_text(row.get("transaction_id")))
        for row in bank_records
    }
    for pair in bank_transfers:
        source = pair["source"]
        src_id = (to_text(source.get("bank_account_id")), to_text(source.get("transaction_id")))
        if pair["status"] not in {"pending", "completed"} and src_id not in visible_ids:
            bank_records.append({  # type: ignore[typeddict-item]
                **source,
                "kind": "bank_transfer",
                "transfer_ids": [pair["id"]],
                "creator_entry_ids": [],
                "categorization_status": "pending",
                "recovery_checkpoint": True,
            })
            visible_ids.add(src_id)
    return bank_suggestions, bank_records


def collect_review_remitter_tokens(
    raw_entries: Sequence[Mapping[str, Any]],
    bank_transactions: Sequence[Mapping[str, Any]],
    transfer_lines: Mapping[tuple[str, str], Any],
) -> list[str]:
    """Collect sorted unique remitter tokens from proposals and non-transfer bank lines."""
    tokens: set[str] = set()
    for entry in raw_entries:
        bank = entry.get("bank")
        if isinstance(bank, Mapping):
            tokens.update(extract_remitter_tokens(bank.get("description")))
        for key in ("ambiguous_candidates", "possible_candidates"):
            for cand in entry.get(key, []):
                tokens.update(extract_remitter_tokens(cand.get("description")))
    for tx in bank_transactions:
        identity = (
            to_text(tx.get("_review_bank_account_id") or tx.get("bank_account_id")),
            to_text(tx.get("transaction_id") or tx.get("id")),
        )
        if identity not in transfer_lines and not is_travel_allowance_withdrawal(tx):
            tokens.update(extract_remitter_tokens(tx.get("description")))
    return sorted(tokens)


def validate_live_bank_line_for_categorization(
    current: Mapping[str, Any],
    proposal: Mapping[str, Any],
    expected_kind: str,
) -> dict[str, object]:
    """Verify live Books bank line matches the reviewed proposal and build base payload."""
    if bank_line_kind(current) != expected_kind:
        raise ReconciliationError("The live bank line classification changed. Refresh before categorizing.")
    if (
        parse_date(current.get("date") or current.get("transaction_date")) != parse_date(proposal.get("date"))
        or to_decimal(current.get("amount")) != to_decimal(proposal.get("amount"))
        or to_text(current.get("description") or current.get("narration")) != to_text(proposal.get("description"))
        or to_text(current.get("reference_number")) != to_text(proposal.get("reference"))
    ):
        raise ReconciliationError("The live bank line changed. Refresh before categorizing.")
    amount = to_decimal(current.get("amount"))
    if amount is None or amount == 0:
        raise ReconciliationError("The bank withdrawal has no valid amount.")
    return {
        "date": to_text(current.get("date") or current.get("transaction_date")),
        "amount": float(abs(amount)),
        "description": to_text(current.get("description") or current.get("narration")),
        "reference_number": to_text(current.get("reference_number")),
    }
