"""Analytics customer-payment inspection, with pure period and series analysis."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from typing import TYPE_CHECKING, TypedDict

from workflows.core.matching import parse_date
from workflows.core.sequences import analyze_number_series, parse_doc_number

if TYPE_CHECKING:
    from zoho.analytics import ZohoAnalyticsAPI


def fetch_customer_payments(analytics: ZohoAnalyticsAPI, workspace_id: str) -> list[dict[str, object]]:
    """Query customer payments from Zoho Analytics."""
    query = """
    SELECT 
        "Payment Number",
        "Payment Date",
        "Payment Mode",
        "Payment Status",
        "Amount (BCY)",
        "Location ID"
    FROM "Customer Payments (Zoho Books)"
    """
    return analytics.queries.execute(
        workspace_id=workspace_id,
        sql_query=query,
        max_attempts=30,
        poll_interval=2.0,
    )


class PaymentSeriesSummary(TypedDict):
    series_prefix: str
    raw_prefix: str
    count: int
    min_number: int | None
    max_number: int | None
    number_range: str
    digit_padding: str
    start_date: str
    end_date: str
    date_range: str
    sample_first: str
    sample_last: str
    top_modes: str
    observed_widths: list[int]
    duplicate_suffixes: list[int]
    missing_count: int
    missing_intervals: list[tuple[int, int]]
    intervals_truncated: bool


def extract_series_info(
    records: Sequence[Mapping[str, object]], start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[list[PaymentSeriesSummary], int]:
    """Filter calendar dates and preserve CLI report fields with bounded gap metadata."""
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date exceeds end_date")
    filtered: list[Mapping[str, object]] = []
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for record in records:
        day = parse_date(record.get("Payment Date"))
        if start_date and (day is None or day < start_date):
            continue
        if end_date and (day is None or day > end_date):
            continue
        filtered.append(record)
        number = str(record.get("Payment Number") or "").strip()
        prefix, _, width = parse_doc_number(number)
        kind = "numeric" if width else "nonnumeric" if number else "empty"
        grouped[(prefix, kind)].append(record)
    summaries: list[PaymentSeriesSummary] = []
    for row in analyze_number_series(filtered, "Payment Number", "Payment Date"):
        prefix, kind = str(row["prefix"]), str(row["kind"])
        items = grouped[(prefix, kind)]
        numbers = sorted(str(item.get("Payment Number") or "").strip() for item in items)
        minimum, maximum = row["min_number"], row["max_number"]
        widths = row["widths"]
        width = max(widths, default=0)
        number_range = f"{minimum:0{width}d} - {maximum:0{width}d}" if minimum is not None else "Non-numeric"
        first_day = date.fromisoformat(str(row["start_date"])).strftime("%d/%m/%Y") if row["start_date"] else "N/A"
        last_day = date.fromisoformat(str(row["end_date"])).strftime("%d/%m/%Y") if row["end_date"] else "N/A"
        modes = Counter(str(item.get("Payment Mode") or "Unknown") for item in items)
        mode_counts = sorted(modes.items(), key=lambda pair: (-pair[1], pair[0]))[:3]
        summaries.append(PaymentSeriesSummary(
            series_prefix="[EMPTY]" if kind == "empty" else prefix or "[Numeric Only]",
            raw_prefix="[EMPTY]" if kind == "empty" else prefix,
            count=int(row["count"]),
            min_number=minimum,
            max_number=maximum,
            number_range=number_range,
            digit_padding=f"{width} digits" if width else "N/A",
            start_date=first_day,
            end_date=last_day,
            date_range=f"{first_day} to {last_day}" if row["start_date"] else "N/A",
            sample_first=numbers[0] if numbers else "",
            sample_last=numbers[-1] if numbers else "",
            top_modes=", ".join(f"{mode} ({count})" for mode, count in mode_counts),
            observed_widths=list(widths),
            duplicate_suffixes=list(row["duplicate_suffixes"]),
            missing_count=int(row["missing_count"]),
            missing_intervals=list(row["missing_intervals"]),
            intervals_truncated=bool(row["intervals_truncated"]),
        ))
    return summaries, len(filtered)


__all__ = ["PaymentSeriesSummary", "fetch_customer_payments", "extract_series_info"]
