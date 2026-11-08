"""Review the original saved scratch evidence through the canonical credit rules."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from utils.file_utils import json
from pathlib import Path
import re
from collections.abc import Sequence
from typing import Any

from workflows.core.matching import parse_date
from zoho.core_sdk.validation import require_record
from .evidence import linked_candidates
from .models import CreditAudit, CreditFinding, RmaCreditPolicy
from .pdf import distinct_memos, parse_credit_memo_text
from .rules import evaluate, flag_shared_links


def _load_records(root: Path, folder: str, id_key: str) -> list[dict[str, Any]]:
    directory = root / folder
    if not directory.is_dir():
        raise ValueError(f"Missing evidence directory: {directory}")
    result = []
    seen = set()
    for path in sorted(directory.glob("*.json")):
        row = require_record(json.loads(path.read_text(encoding="utf-8")), str(path))
        key = str(row.get(id_key) or "")
        if not key or key in seen:
            raise ValueError(f"Missing/duplicate {id_key} in {path}")
        seen.add(key)
        result.append(row)
    return result


def review_saved_polycab_vendor_credits(
    directory: Path, *, policy: RmaCreditPolicy, from_date: date, to_date: date,
    credit_numbers: Sequence[str] = (),
) -> list[CreditAudit]:
    """Offline review of credits/, texts/, journals/ and payments/ evidence.

    Uses saved extraction text and canonical parsing/linkage/accounting rules.
    It never fetches live data or approves writes from historical evidence.
    Missing PDF text is an explicit blocking finding, rather than an omitted PDF.
    """
    if from_date > to_date:
        raise ValueError("Credit date range is reversed")
    credits = _load_records(directory, "credits", "vendor_credit_id")
    journals = _load_records(directory, "journals", "journal_id")
    payments = _load_records(directory, "payments", "payment_id")
    selected = []
    for credit in credits:
        if credit.get("vendor_id") != policy.vendor_id:
            continue
        day = parse_date(credit.get("date"))
        if day is None:
            raise ValueError("Saved credit has an invalid date")
        if from_date <= day <= to_date and (not credit_numbers or credit.get("vendor_credit_number") in credit_numbers):
            selected.append(credit)
    numbers = [credit["vendor_credit_number"] for credit in selected]
    if len(set(numbers)) != len(numbers):
        raise ValueError("Ambiguous saved vendor credit numbers")
    missing = set(credit_numbers) - set(numbers)
    if missing:
        raise ValueError("Selected credits missing from saved scope: " + ", ".join(sorted(missing)))
    audits = []
    for credit in selected:
        memos = []
        findings = [CreditFinding("saved_evidence", "Historical evidence requires a fresh live review before correction", True)]
        number = str(credit["vendor_credit_number"]).replace("/", "_")
        for doc in credit.get("documents", []) or []:
            try:
                document_id = str(doc["document_id"])
                if not re.fullmatch(r"[A-Za-z0-9_-]+", number) or not re.fullmatch(r"[A-Za-z0-9_-]+", document_id):
                    raise ValueError("Unsafe saved attachment filename")
                path = directory / "texts" / f"{number}_{document_id}.txt"
                memo = parse_credit_memo_text(path.read_text(encoding="utf-8"))
                memos.append(replace(memo, document_id=document_id, source_path=str(path.resolve())))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                findings.append(CreditFinding("pdf_error", f"Saved attachment {doc}: {exc}", True))
        try:
            evidence = distinct_memos(tuple(memos))
        except ValueError as exc:
            findings.append(CreditFinding("pdf_error", str(exc), True))
            evidence = ()
        audit = CreditAudit(credit, evidence, None, None, findings)
        if audit.is_rma:
            for kind, rows in (("journal", journals), ("payment", payments)):
                scoped = [row for row in rows if (from_date <= date.fromisoformat(row["journal_date"]) <= to_date
                          if kind == "journal" else row.get("customer_id") == policy.customer_id)]
                match, link = linked_candidates(credit, evidence, scoped, kind=kind)
                setattr(audit, kind, match)
                setattr(audit, kind + "_link", link)
        audits.append(evaluate(audit, policy))
    return flag_shared_links(audits)
