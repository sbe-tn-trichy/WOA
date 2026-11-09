from __future__ import annotations

import calendar
import logging
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import datetime
from typing import Literal, Protocol, TypedDict, cast, overload

from utils.general_utils.sequences import parse_doc_number
from utils.http_utils import http_transport
from utils.http_utils.http import write_response_to_file
from zoho.core_sdk.base_client import BaseZohoClient
from zoho.core_sdk.exceptions import ZohoBooksError
from zoho.core_sdk.security import resolve_output_path
from ..base import BaseResource

logger = logging.getLogger("zoho_books")


class BooksGstClient(Protocol):
    @property
    def invoices(self) -> BaseResource: ...

    @property
    def credit_notes(self) -> BaseResource: ...


class _ConformingDoc(TypedDict):
    doc: Mapping[str, object]
    number: str
    date: str
    prefix: str
    seq: int
    width: int


class GST(BaseResource):
    """
    Helper resource under ZohoBooksAPI to run GST validation checks.
    """

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "gst")

    @property
    def books_client(self) -> BooksGstClient:
        return cast(BooksGstClient, self.client)

    def get_month_date_range(self, month_str: str) -> tuple[str, str]:
        """
        Parses a month string ('YYYY-MM') and returns ('YYYY-MM-01', 'YYYY-MM-DD').
        """
        try:
            dt = datetime.strptime(month_str.strip(), "%Y-%m")
            year = dt.year
            month = dt.month
            _, last_day = calendar.monthrange(year, month)
            return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"
        except ValueError as e:
            raise ValueError(
                f"Invalid month format '{month_str}'. Must be 'YYYY-MM'."
            ) from e

    def validate_gst_data(self, month_str: str) -> dict[str, object]:
        """
        Executes outward GST validations:
        1. Checks invoice number sequence gaps and chronology.
        2. Checks credit note number sequence gaps and chronology.
        3. Lists draft and void documents.
        4. Summarizes HSN and GST rate-wise taxable value, tax, and total.
        """
        start_date, end_date = self.get_month_date_range(month_str)
        logger.info(
            f"Running GST validations for date range {start_date} to {end_date}..."
        )

        # 1. Fetch Invoices and Credit Notes
        params: dict[str, object] = {"date_start": start_date, "date_end": end_date}
        invoices = self.books_client.invoices.list_all(params=params)
        credit_notes = self.books_client.credit_notes.list_all(params=params)

        # 2. Run validations
        invoice_results = self._validate_document_sequence_and_status(
            invoices, "invoice_number", "invoice_id", "date"
        )
        cn_results = self._validate_document_sequence_and_status(
            credit_notes, "creditnote_number", "creditnote_id", "date"
        )

        # 3. Fetch detailed data for calculation (excluding draft/void)
        active_invoices = [
            inv for inv in invoices if inv.get("status") not in ("draft", "void")
        ]
        active_credit_notes = [
            cn for cn in credit_notes if cn.get("status") not in ("draft", "void")
        ]

        detailed_invoices = self._fetch_details_concurrently(
            self.books_client.invoices, active_invoices, "invoice_id", "invoice"
        )
        detailed_credit_notes = self._fetch_details_concurrently(
            self.books_client.credit_notes,
            active_credit_notes,
            "creditnote_id",
            "creditnote",
        )

        # 4. Generate HSN & GST% Tax Summary
        summary = self._generate_tax_summary(detailed_invoices, detailed_credit_notes)

        return {
            "month": month_str,
            "date_range": (start_date, end_date),
            "invoices": {
                "total_count": len(invoices),
                "active_count": len(active_invoices),
                "draft": invoice_results["draft"],
                "void": invoice_results["void"],
                "missing": invoice_results["missing"],
                "out_of_chronology": invoice_results["out_of_chronology"],
            },
            "credit_notes": {
                "total_count": len(credit_notes),
                "active_count": len(active_credit_notes),
                "draft": cn_results["draft"],
                "void": cn_results["void"],
                "missing": cn_results["missing"],
                "out_of_chronology": cn_results["out_of_chronology"],
            },
            "tax_summary": summary,
        }

    def _validate_document_sequence_and_status(
        self,
        docs: Sequence[Mapping[str, object]],
        num_key: str,
        id_key: str,
        date_key: str,
    ) -> dict[str, object]:
        """
        Performs status classification and sequence/chronological order check on list of documents.
        """
        draft_docs: list[dict[str, object]] = []
        void_docs: list[dict[str, object]] = []
        conforming_docs: list[_ConformingDoc] = []

        for doc in docs:
            num = str(doc.get(num_key) or "")
            status = str(doc.get("status", "")).lower()
            doc_id = doc.get(id_key)
            date_val = str(doc.get(date_key, ""))

            # 1. Check statuses
            info: dict[str, object] = {
                "id": doc_id,
                "number": num,
                "date": date_val,
                "status": doc.get("status"),
            }
            if status == "draft":
                draft_docs.append(info)
            elif status == "void":
                void_docs.append(info)

            # Parse document number for sequence checking
            prefix, seq, width = parse_doc_number(num)
            if seq > 0:
                conforming_docs.append(
                    {
                        "doc": doc,
                        "number": num,
                        "date": date_val,
                        "prefix": prefix,
                        "seq": seq,
                        "width": width,
                    }
                )

        # 2. Group by prefix
        groups: dict[str, list[_ConformingDoc]] = {}
        for item in conforming_docs:
            prefix = item["prefix"]
            groups.setdefault(prefix, []).append(item)

        missing_numbers: list[str] = []
        out_of_chronology: list[dict[str, object]] = []

        # 3. Analyze each prefix group
        for prefix, items in groups.items():
            # Sort by sequence number
            items.sort(key=lambda x: x["seq"])

            # Check for sequence gaps
            seqs_found = {x["seq"] for x in items}
            min_seq = min(seqs_found)
            max_seq = max(seqs_found)

            for s in range(min_seq, max_seq + 1):
                if s not in seqs_found:
                    width = items[0]["width"]
                    missing_num = f"{prefix}{s:0{width}d}"
                    missing_numbers.append(missing_num)

            # Check for chronological order violation
            for idx in range(1, len(items)):
                prev_item = items[idx - 1]
                curr_item = items[idx]

                prev_date = str(prev_item["date"])
                curr_date = str(curr_item["date"])

                if curr_date < prev_date:
                    out_of_chronology.append(
                        {
                            "number": curr_item["number"],
                            "date": curr_date,
                            "preceded_by": prev_item["number"],
                            "preceding_date": prev_date,
                            "message": f"Document {curr_item['number']} (Date: {curr_date}) is dated earlier than preceding document {prev_item['number']} (Date: {prev_date}) in sequence.",
                        }
                    )

        return {
            "draft": draft_docs,
            "void": void_docs,
            "missing": sorted(missing_numbers),
            "out_of_chronology": out_of_chronology,
        }

    def _fetch_details_concurrently(
        self,
        client_module: BaseResource,
        docs: Sequence[Mapping[str, object]],
        id_key: str,
        doc_key: str,
    ) -> list[dict[str, object]]:
        """
        Fetch complete details with bounded concurrency; transport owns retries.
        """
        if not docs:
            return []

        identifiers = [str(doc.get(id_key) or "").strip() for doc in docs]
        if not all(identifiers) or len(set(identifiers)) != len(identifiers):
            raise ZohoBooksError(
                f"GST {doc_key} list has missing or duplicate {id_key}; summary aborted."
            )

        def fetch_one(doc_id: str) -> dict[str, object]:
            try:
                response = client_module.get(doc_id)
            except Exception as exc:
                raise ZohoBooksError(
                    f"GST summary incomplete: failed to fetch {doc_key} {doc_id}.",
                    status_code=getattr(exc, "status_code", None),
                    error_code=getattr(exc, "error_code", None),
                ) from exc
            detail = response.get(doc_key) if isinstance(response, Mapping) else None
            if (
                not isinstance(detail, Mapping)
                or str(detail.get(id_key)) != doc_id
                or not isinstance(detail.get("line_items"), list)
            ):
                raise ZohoBooksError(
                    f"GST summary incomplete: invalid {doc_key} detail for {doc_id}."
                )
            return dict(detail)

        workers = min(5, len(docs))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(copy_context().run, fetch_one, doc_id)
                for doc_id in identifiers
            ]
            return [future.result() for future in futures]

    def _generate_tax_summary(
        self,
        detailed_invoices: Sequence[Mapping[str, object]],
        detailed_credit_notes: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        """
        Aggregates taxable value, tax, and totals grouped by HSN and GST rate.
        Generates separate sums for Invoices, Credit Notes, and Net Consolidated.
        """

        def init_agg() -> dict[str, float]:
            return {"taxable": 0.0, "tax": 0.0, "total": 0.0}

        inv_agg: dict[tuple[str, float], dict[str, float]] = {}
        cn_agg: dict[tuple[str, float], dict[str, float]] = {}
        net_agg: dict[tuple[str, float], dict[str, float]] = {}

        # Aggregate invoices
        for inv in detailed_invoices:
            raw_items = inv.get("line_items", [])
            items = raw_items if isinstance(raw_items, list) else []
            for raw_item in items:
                if not isinstance(raw_item, Mapping):
                    continue
                hsn = raw_item.get("hsn_or_sac")
                if not hsn:
                    hsn = "N/A"
                hsn = str(hsn).strip()
                gst_pct = float(raw_item.get("tax_percentage", 0) or 0)

                key = (hsn, gst_pct)
                taxable = float(raw_item.get("item_total", 0.0) or 0.0)
                taxes = raw_item.get("line_item_taxes", [])
                tax_val = sum(
                    float(tax.get("tax_amount", 0.0) or 0.0)
                    for tax in taxes
                    if isinstance(tax, Mapping)
                )

                # Update Invoice Aggregation
                inv_entry = inv_agg.setdefault(key, init_agg())
                inv_entry["taxable"] += taxable
                inv_entry["tax"] += tax_val
                inv_entry["total"] += taxable + tax_val

                # Update Net Aggregation
                net_entry = net_agg.setdefault(key, init_agg())
                net_entry["taxable"] += taxable
                net_entry["tax"] += tax_val
                net_entry["total"] += taxable + tax_val

        # Aggregate credit notes
        for cn in detailed_credit_notes:
            raw_items = cn.get("line_items", [])
            items = raw_items if isinstance(raw_items, list) else []
            for raw_item in items:
                if not isinstance(raw_item, Mapping):
                    continue
                hsn = raw_item.get("hsn_or_sac")
                if not hsn:
                    hsn = "N/A"
                hsn = str(hsn).strip()
                gst_pct = float(raw_item.get("tax_percentage", 0) or 0)

                key = (hsn, gst_pct)
                taxable = float(raw_item.get("item_total", 0.0) or 0.0)
                taxes = raw_item.get("line_item_taxes", [])
                tax_val = sum(
                    float(tax.get("tax_amount", 0.0) or 0.0)
                    for tax in taxes
                    if isinstance(tax, Mapping)
                )

                # Update CN Aggregation
                cn_entry = cn_agg.setdefault(key, init_agg())
                cn_entry["taxable"] += taxable
                cn_entry["tax"] += tax_val
                cn_entry["total"] += taxable + tax_val

                # Update Net Aggregation (Subtract Credit Notes)
                net_entry = net_agg.setdefault(key, init_agg())
                net_entry["taxable"] -= taxable
                net_entry["tax"] -= tax_val
                net_entry["total"] -= taxable + tax_val

        def finalize_summary(
            agg: Mapping[tuple[str, float], Mapping[str, float]],
        ) -> list[dict[str, object]]:
            final: list[dict[str, object]] = []
            for (hsn, gst), vals in sorted(
                agg.items(), key=lambda x: (x[0][0], x[0][1])
            ):
                final.append(
                    {
                        "hsn_or_sac": hsn,
                        "gst_percentage": gst,
                        "taxable_value": round(vals["taxable"], 2),
                        "tax_amount": round(vals["tax"], 2),
                        "total": round(vals["total"], 2),
                    }
                )
            return final

        return {
            "invoices": finalize_summary(inv_agg),
            "credit_notes": finalize_summary(cn_agg),
            "consolidated": finalize_summary(net_agg),
        }

    @overload
    def get_gstr_outward_supplies(
        self,
        params: Mapping[str, object] | None = None,
        *,
        stream: Literal[True],
    ) -> http_transport.Response: ...

    @overload
    def get_gstr_outward_supplies(
        self,
        params: Mapping[str, object] | None = None,
        *,
        stream: Literal[False] = False,
    ) -> object: ...

    @overload
    def get_gstr_outward_supplies(
        self,
        params: Mapping[str, object] | None = None,
        *,
        stream: bool = False,
    ) -> object: ...

    def get_gstr_outward_supplies(
        self,
        params: Mapping[str, object] | None = None,
        *,
        stream: bool = False,
    ) -> object:
        """
        Retrieve GSTR-1 Outward Supplies report content (e.g. XLSX, XLS or PDF).
        """
        if stream:
            return self.client.request(
                "GET",
                "reports/gstroutwardsupplies",
                params=dict(params) if params else None,
                stream=True,
            )
        return self.client.request(
            "GET", "reports/gstroutwardsupplies", params=dict(params) if params else None
        )

    def download_gstr_outward_supplies(
        self,
        save_path: str,
        params: Mapping[str, object] | None = None,
    ) -> str:
        """
        Download GSTR-1 Outward Supplies report and save it to the specified path.
        """
        params_dict: dict[str, object] = dict(params or {})
        if "accept" not in params_dict:
            params_dict["accept"] = "xlsx"

        resolved_path = resolve_output_path(save_path)
        response = self.get_gstr_outward_supplies(params=params_dict, stream=True)
        return write_response_to_file(response, resolved_path)

    @overload
    def get_gstr_inward_supplies(
        self,
        params: Mapping[str, object] | None = None,
        *,
        stream: Literal[True],
    ) -> http_transport.Response: ...

    @overload
    def get_gstr_inward_supplies(
        self,
        params: Mapping[str, object] | None = None,
        *,
        stream: Literal[False] = False,
    ) -> object: ...

    @overload
    def get_gstr_inward_supplies(
        self,
        params: Mapping[str, object] | None = None,
        *,
        stream: bool = False,
    ) -> object: ...

    def get_gstr_inward_supplies(
        self,
        params: Mapping[str, object] | None = None,
        *,
        stream: bool = False,
    ) -> object:
        """
        Retrieve GSTR-2 Inward Supplies report content (e.g. XLSX, XLS or PDF).
        """
        if stream:
            return self.client.request(
                "GET",
                "reports/gstrinwardsupplies",
                params=dict(params) if params else None,
                stream=True,
            )
        return self.client.request(
            "GET", "reports/gstrinwardsupplies", params=dict(params) if params else None
        )

    def download_gstr_inward_supplies(
        self,
        save_path: str,
        params: Mapping[str, object] | None = None,
    ) -> str:
        """
        Download GSTR-2 Inward Supplies report and save it to the specified path.
        """
        params_dict: dict[str, object] = dict(params or {})
        if "accept" not in params_dict:
            params_dict["accept"] = "xlsx"

        resolved_path = resolve_output_path(save_path)
        response = self.get_gstr_inward_supplies(params=params_dict, stream=True)
        return write_response_to_file(response, resolved_path)
