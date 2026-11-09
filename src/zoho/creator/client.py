from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from zoho.core_sdk.base_client import BaseZohoClient
from .exceptions import ZohoCreatorError

logger = logging.getLogger("zoho.creator.api")


class ZohoCreatorAPI(BaseZohoClient):
    """
    Client for Zoho Creator API v2.1.
    Docs: https://www.zoho.com/creator/help/api/v2.1/
    """
    def __init__(
        self,
        access_token: str,
        account_owner_name: str,
        domain: str = "in",
        environment: str = "production",
        send_environment_header: bool = True,
        token_refresh_callback: Callable[[BaseZohoClient], None] | Callable[[], str] | None = None,
    ):
        base_url = f"https://www.zohoapis.{domain or 'in'}/creator/v2.1"
        super().__init__(
            access_token=access_token,
            domain=domain or "in",
            base_url=base_url,
            service_name="creator",
            token_refresh_callback=token_refresh_callback,
            default_timeout=30,
        )
        self.account_owner_name = account_owner_name
        self.environment = environment or "production"
        self.send_environment_header = send_environment_header

    def request(
        self,
        method: str,
        endpoint: str,
        json: Mapping[str, object] | Sequence[object] | None = None,
        data: Mapping[str, object] | str | bytes | None = None,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        files: Mapping[str, object] | None = None,
        stream: bool = False,
        override_url: str | None = None,
        is_mutation: bool | None = None,
        timeout: int | None = None,
    ) -> object:
        req_headers: dict[str, str] = {}
        if self.send_environment_header:
            req_headers["environment"] = self.environment
        if headers:
            req_headers.update(headers)
        return super().request(
            method=method,
            endpoint=endpoint,
            json=json,
            data=data,
            params=params,
            headers=req_headers,
            files=files,
            stream=stream,
            override_url=override_url,
            is_mutation=is_mutation,
            timeout=timeout,
        )

    # ==========================================
    # 1. Native Metadata APIs
    # ==========================================
    def list_applications(self) -> object:
        """Gets metadata of all applications."""
        return self.request("GET", f"meta/{self.account_owner_name}/applications")

    def list_forms(self, app_link_name: str) -> object:
        """Gets metadata of all forms in an application."""
        return self.request("GET", f"meta/{self.account_owner_name}/{app_link_name}/forms")

    def list_reports(self, app_link_name: str) -> object:
        """Gets metadata of all reports in an application."""
        return self.request("GET", f"meta/{self.account_owner_name}/{app_link_name}/reports")

    def get_fields(self, app_link_name: str, form_link_name: str) -> object:
        """Gets metadata of all fields in a form."""
        return self.request("GET", f"meta/{self.account_owner_name}/{app_link_name}/form/{form_link_name}/fields")

    # ==========================================
    # 2. Native Data APIs
    # ==========================================
    def get_records(
        self,
        app_link_name: str,
        report_link_name: str,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> object:
        """Fetches records from a report (up to 1000 records)."""
        if headers is not None:
            return self.request(
                "GET",
                f"data/{self.account_owner_name}/{app_link_name}/report/{report_link_name}",
                params=params,
                headers=headers,
            )
        return self.request(
            "GET",
            f"data/{self.account_owner_name}/{app_link_name}/report/{report_link_name}",
            params=params,
        )

    def download_file(
        self,
        app_link_name: str,
        report_link_name: str,
        record_id: str,
        field_link_name: str,
        destination: str | Path,
        *,
        filepath: str | None = None,
    ) -> str:
        """Download one report attachment to a caller-selected local path.

        Pass the API-returned filepath for fields supporting multiple uploads.
        Attachment URLs are never followed, keeping OAuth on the API host.
        """
        from urllib.parse import quote
        from utils.http_utils.http import write_response_to_file

        parts = (self.account_owner_name, app_link_name, report_link_name,
                 record_id, field_link_name)
        if any(not str(part).strip() for part in parts):
            raise ValueError("Owner, app, report, record and field are required.")
        owner, app, report, record, field = (quote(str(part), safe="") for part in parts)
        response = self.request(
            "GET", f"data/{owner}/{app}/report/{report}/{record}/{field}/download",
            params={"filepath": filepath} if filepath else None, stream=True,
        )
        return write_response_to_file(response, str(destination))

    def add_records(
        self,
        app_link_name: str,
        form_link_name: str,
        payload: Mapping[str, object],
        params: Mapping[str, object] | None = None,
    ) -> object:
        """Adds record(s) to a form (payload format: {"data": [...]})."""
        return self.request("POST", f"data/{self.account_owner_name}/{app_link_name}/form/{form_link_name}", json=payload, params=params)

    def update_records(
        self,
        app_link_name: str,
        report_link_name: str,
        payload: Mapping[str, object],
        record_id: str | None = None,
        params: Mapping[str, object] | None = None,
    ) -> object:
        """Updates record(s) in a report by ID or criteria (payload: {"data": {...}})."""
        endpoint = f"data/{self.account_owner_name}/{app_link_name}/report/{report_link_name}"
        if record_id:
            endpoint = f"{endpoint}/{record_id}"
        return self.request("PATCH", endpoint, json=payload, params=params)

    def delete_records(
        self,
        app_link_name: str,
        report_link_name: str,
        record_id: str | None = None,
        params: Mapping[str, object] | None = None,
    ) -> object:
        """Deletes record(s) in a report by ID or criteria."""
        endpoint = f"data/{self.account_owner_name}/{app_link_name}/report/{report_link_name}"
        if record_id:
            endpoint = f"{endpoint}/{record_id}"
        return self.request("DELETE", endpoint, params=params)

    # ==========================================
    # 3. Custom SDK Functions
    # ==========================================
    def get_all_records(
        self,
        app_link_name: str,
        report_link_name: str,
        criteria: str | None = None,
        *,
        field_config: str | None = None,
    ) -> list[dict[str, object]]:
        """
        Custom function: Auto-paginates using record_cursor to fetch all records.
        """
        all_records: list[dict[str, object]] = []
        params: dict[str, object] = {"max_records": 1000}
        if field_config:
            params["field_config"] = field_config
        if criteria:
            params["criteria"] = criteria

        res = self.get_records(app_link_name, report_link_name, params=params)

        raw_data = res.get("data", []) if isinstance(res, dict) else []
        if isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict):
                    all_records.append(item)

        # Loop while cursor exists in the response
        seen_cursors: set[str] = set()
        while True:
            page_context = res.get("page_context", {}) if isinstance(res, dict) else {}
            if isinstance(page_context, dict) and "has_more_page" in page_context and not page_context["has_more_page"]:
                break

            cursor = (page_context.get("record_cursor") if isinstance(page_context, dict) else None) or (res.get("record_cursor") if isinstance(res, dict) else None)
            if not cursor or not isinstance(cursor, str) or cursor in seen_cursors:
                break
            seen_cursors.add(cursor)

            # Query next page using cursor in header
            headers = {"record_cursor": cursor}
            res = (
                self.get_records(app_link_name, report_link_name, headers=headers, params={"field_config": field_config})
                if field_config
                else self.get_records(app_link_name, report_link_name, headers=headers)
            )
            raw_data = res.get("data", []) if isinstance(res, dict) else []
            if isinstance(raw_data, list):
                for item in raw_data:
                    if isinstance(item, dict):
                        all_records.append(item)
            if not raw_data:
                break

        return all_records

    def add_records_bulk(
        self,
        app_link_name: str,
        form_link_name: str,
        records: Sequence[Mapping[str, object]],
        skip_workflow: Sequence[str] | None = None,
    ) -> list[object]:
        """
        Custom function: Bulk adds records by chunking them into batches of 200.
        """
        responses: list[object] = []
        # Chunk records in batches of 200
        for i in range(0, len(records), 200):
            chunk = list(records[i:i+200])
            payload: dict[str, object] = {"data": chunk}
            if skip_workflow:
                payload["skip_workflow"] = list(skip_workflow)
            res = self.add_records(app_link_name, form_link_name, payload)
            responses.append(res)
        return responses

