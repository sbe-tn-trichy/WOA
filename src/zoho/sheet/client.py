from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence

from utils.file_utils import json
from zoho.core_sdk.base_client import BaseZohoClient

logger = logging.getLogger("zoho.sheet")


class ZohoSheetAPI(BaseZohoClient):
    """
    Client for Zoho Sheet API v2.
    Docs: https://www.zoho.com/sheet/help/api/v2/
    """
    def __init__(
        self,
        access_token: str,
        domain: str = "in",
        token_refresh_callback: Callable[[BaseZohoClient], None] | Callable[[], str] | None = None,
    ):
        base_url = f"https://sheet.zoho.{domain or 'in'}/api/v2"
        super().__init__(
            access_token=access_token,
            domain=domain or "in",
            base_url=base_url,
            service_name="sheet",
            token_refresh_callback=token_refresh_callback,
        )

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Zoho-oauthtoken {str(self.access_token)}"
        }

    def list_workbooks(self) -> list[dict[str, object]]:
        """Lists all workbooks in the user's account."""
        params = {"method": "workbook.list"}
        res = self.request("GET", "workbooks", params=params)
        raw_wb = res.get('workbooks', []) if isinstance(res, dict) else []
        return [w for w in raw_wb if isinstance(w, dict)] if isinstance(raw_wb, list) else []

    def list_sheets(self, workbook_id: str) -> list[str]:
        """Lists all worksheets in a workbook."""
        params = {"method": "worksheet.list"}
        res = self.request("POST", workbook_id, params=params, is_mutation=False)
        worksheets = res.get('worksheet_names', []) if isinstance(res, dict) else []
        if not isinstance(worksheets, list):
            return []
        return [
            str(item.get("worksheet_name") or item.get("name"))
            if isinstance(item, dict) else str(item)
            for item in worksheets
            if not isinstance(item, dict)
            or item.get("worksheet_name") is not None
            or item.get("name") is not None
        ]

    def get_sheet_id(self, workbook_id: str, sheet_name: str) -> str:
        """Return the worksheet ID required by workbook range-format APIs."""
        res = self.request("POST", workbook_id, params={"method": "worksheet.list"}, is_mutation=False)
        names = res.get("worksheet_names", []) if isinstance(res, dict) else []
        if isinstance(names, list):
            for worksheet in names:
                if isinstance(worksheet, dict) and worksheet.get("worksheet_name") == sheet_name:
                    return str(worksheet["worksheet_id"])
        raise ValueError(f"Worksheet {sheet_name!r} was not found.")

    def format_ranges(self, workbook_id: str, formats: Sequence[Mapping[str, object]]) -> object:
        """Apply Zoho Sheet range formats in one workbook request."""
        return self.request(
            "POST", workbook_id, params={"method": "ranges.format.set"},
            data={"format_json": json.dumps(list(formats))}, is_mutation=True,
        )

    def delete_rows(self, workbook_id: str, sheet_name: str, row_indices: Sequence[int]) -> object:
        """Delete specific tabular rows using their Zoho row indices."""
        if not row_indices:
            return {}
        return self.request(
            "POST", workbook_id, params={"method": "worksheet.records.delete"},
            data={"worksheet_name": sheet_name, "row_array": json.dumps(list(row_indices))},
            is_mutation=True,
        )

    def get_rows(self, workbook_id: str, sheet_name: str, limit: int = 1) -> list[object]:
        """Fetches rows from a specific sheet. Returns empty list if sheet has no records."""
        params: dict[str, object] = {
            "method": "worksheet.records.fetch",
            "worksheet_name": sheet_name,
            "limit": limit,
        }
        try:
            res = self.request("GET", workbook_id, params=params)
            if isinstance(res, dict):
                error_code = res.get("error_code")
                if error_code == 2884:
                    return []
                if error_code or res.get("status") == "error":
                    from zoho.core_sdk.exceptions import ZohoSheetError
                    raise ZohoSheetError(
                        str(res.get("error_message") or res.get("message") or f"Sheet Error (code={error_code})"),
                        error_code=error_code if isinstance(error_code, int) else None,
                        response_data=res,
                    )
            raw_rec = res.get('records', []) if isinstance(res, dict) else []
            return list(raw_rec) if isinstance(raw_rec, list) else []
        except Exception as e:
            if "2884" in str(e):
                return []
            raise

    def set_content(self, workbook_id: str, sheet_name: str, range_addr: str, data: Sequence[Sequence[object]]) -> object:
        """
        Sets content of a range of cells.
        Note: worksheet.content.set is currently returning 2867 (unsupported) in some environments.
        Use set_cell for individual headers if this fails.
        """
        params = {"method": "worksheet.content.set"}
        payload = {
            "worksheet_name": sheet_name,
            "range": range_addr,
            "json_data": json.dumps(list(data)),
        }
        return self.request("POST", workbook_id, params=params, data=payload, is_mutation=True)

    def set_cell(self, workbook_id: str, sheet_name: str, row: int, col: int, content: object) -> object:
        """Sets content of a single cell using cell.content.set (guaranteed to work in v2)."""
        params = {"method": "cell.content.set"}
        payload = {
            "worksheet_name": sheet_name,
            "row": row,
            "column": col,
            "content": str(content),
        }
        return self.request("POST", workbook_id, params=params, data=payload, is_mutation=True)

    def add_sheet(self, workbook_id: str, sheet_name: str) -> object:
        """Adds a new sheet to an existing workbook."""
        params = {"method": "worksheet.insert"}
        payload = {
            "worksheet_name": sheet_name,
        }
        return self.request("POST", workbook_id, params=params, data=payload, is_mutation=True)

    def add_rows(self, workbook_id: str, sheet_name: str, rows_data: Sequence[Sequence[object]] | Sequence[Mapping[str, object]], header_row: int = 1) -> object:
        """
        Appends rows to a specific sheet using tabular records API.
        rows_data can be a list of lists or a list of dicts.
        """
        params = {"method": "worksheet.records.add"}
        payload = {
            "worksheet_name": sheet_name,
            "json_data": json.dumps(list(rows_data)),
            "header_row": header_row,
        }
        return self.request("POST", workbook_id, params=params, data=payload, is_mutation=True)

    def update_rows(self, workbook_id: str, sheet_name: str, criteria: str, rows_data: Mapping[str, object]) -> object:
        """Updates rows matching a criteria."""
        params = {"method": "worksheet.records.update"}
        payload = {
            "worksheet_name": sheet_name,
            "criteria": criteria,
            "data": json.dumps(dict(rows_data)),
        }
        return self.request("POST", workbook_id, params=params, data=payload, is_mutation=True)

    def truncate_sheet(self, workbook_id: str, sheet_name: str, criteria: str = "(row_index != 0)") -> object:
        """Deletes rows in a sheet based on criteria."""
        params = {"method": "worksheet.records.delete"}
        payload = {
            "worksheet_name": sheet_name,
            "criteria": criteria,
        }
        return self.request("POST", workbook_id, params=params, data=payload, is_mutation=True)

    def clear_range(
        self,
        workbook_id: str,
        sheet_name: str,
        start_row: int,
        start_col: int,
        end_row: int,
        end_col: int,
    ) -> object:
        """Clears content across a specified range using range.clear."""
        params = {"method": "range.clear"}
        payload: dict[str, object] = {
            "worksheet_name": sheet_name,
            "start_row": start_row,
            "start_column": start_col,
            "end_row": end_row,
            "end_column": end_col,
        }
        return self.request("POST", workbook_id, params=params, data=payload, is_mutation=True)
