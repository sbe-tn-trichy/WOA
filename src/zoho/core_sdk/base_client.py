import contextlib
import threading
import time
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

from utils.http_utils import http, http_transport
from zoho.core_sdk.exceptions import (
    ZohoAnalyticsError,
    ZohoBooksError,
    ZohoCliqError,
    ZohoConfigurationError,
    ZohoCreatorError,
    ZohoERPError,
    ZohoError,
    ZohoInventoryError,
    ZohoMailError,
    ZohoSheetError,
    ZohoTokenResponseError,
    ZohoWorkdriveError,
)
from zoho.core_sdk.logging import configure_service_logger
from zoho.core_sdk.security import sanitize_log_params, sanitize_log_url

_ERROR_MAP = {
    "erp": ZohoERPError,
    "books": ZohoBooksError,
    "inventory": ZohoInventoryError,
    "wd": ZohoWorkdriveError,
    "mail": ZohoMailError,
    "creator": ZohoCreatorError,
    "cliq": ZohoCliqError,
    "sheet": ZohoSheetError,
    "analytics": ZohoAnalyticsError,
}

_KEEP_NONE_KEYS: dict[str, frozenset[str]] = {
    "books": frozenset({"json", "files"}),
    "inventory": frozenset({"json", "files"}),
    "mail": frozenset({"params", "json", "files"}),
    "creator": frozenset({"params", "json"}),
}


class BaseZohoClient:
    """
    Unified base client for all Zoho API services.
    Handles credentials, request execution, timeouts, logger setup,
    domain resolution, and unified automatic 401 token refresh retries.
    """
    def __init__(
        self,
        access_token: Any,
        domain: str = "in",
        base_url: str = "",
        service_name: str = "",
        token_refresh_callback: Any | None = None,
        on_request_completed: Any | None = None,
        default_timeout: int = 30
    ):
        resolved_domain = (domain or "").strip().lower()
        if resolved_domain != "in":
            raise ZohoConfigurationError(
                f"Only Zoho India ('in') domain is supported; got {domain!r}."
            )
        self.access_token = access_token
        self.domain = "in"
        self.base_url = base_url
        self.service_name = service_name
        self.token_refresh_callback = token_refresh_callback
        self.on_request_completed = on_request_completed
        self.default_timeout = default_timeout
        self.session = http_transport.Session()
        self._token_lock = threading.Lock()
        self._setup_loggers()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        if hasattr(self, "session") and self.session is not None:
            with contextlib.suppress(Exception):
                self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _setup_loggers(self) -> None:
        self.logger = configure_service_logger(self.service_name)

    def _determine_is_mutation(self, method: str, is_mutation: bool | None = None) -> bool:
        if is_mutation is not None:
            return is_mutation
        return method.upper() in ("POST", "PUT", "PATCH", "DELETE")

    def _build_headers(
        self,
        token: str,
        method: str,
        headers: dict[str, Any] | None,
        has_files: bool,
        has_data: bool,
    ) -> dict[str, str]:
        req_headers = {"Authorization": f"Zoho-oauthtoken {token}"}
        if headers:
            req_headers.update(headers)

        if not has_files and not has_data and "Content-Type" not in req_headers:
            if self.service_name == "wd":
                req_headers["Accept"] = "application/vnd.api+json"
            elif self.service_name == "creator":
                if method.upper() in ("POST", "PUT", "PATCH"):
                    req_headers["Content-Type"] = "application/json"
            elif self.service_name != "sheet":
                req_headers["Content-Type"] = "application/json"
        return req_headers

    def _parse_error(
        self, response: http_transport.Response
    ) -> tuple[Any, Any, str]:
        try:
            error_data = response.json()
        except Exception:
            error_data = None

        code = None
        message = None
        if isinstance(error_data, dict):
            code = error_data.get("code")
            if code is None:
                code = error_data.get("error_code")
            message = (
                error_data.get("message")
                or error_data.get("description")
                or error_data.get("error_message")
            )

        if not message:
            message = http.sanitize_error_text(
                response.text, response.status_code, response.reason
            )
        return error_data, code, str(message)

    def _raise_for_status(
        self, response: http_transport.Response, endpoint: str | None = None
    ) -> None:
        if response.status_code < 400:
            return

        error_data, code, message = self._parse_error(response)
        if code is None:
            description = f"HTTP Error: {response.status_code} - {message}"
        else:
            description = f"API Error (code={code}): {message}"

        error_class = _ERROR_MAP.get(self.service_name, ZohoError)
        raise error_class(
            description,
            status_code=response.status_code,
            error_code=code,
            response_data=error_data,
            endpoint=endpoint,
            retry_after=http.extract_retry_after(response.headers),
        )

    def _resolve_token(self, token_source: Any, is_mutation: bool) -> str:
        if hasattr(token_source, "get_token_for_request"):
            return token_source.get_token_for_request(is_mutation)
        return str(token_source)

    def _is_rate_limited(self, response: http_transport.Response) -> bool:
        if response.status_code == 429:
            return True
        if response.status_code < 400:
            return False

        try:
            error_data = response.json()
        except ValueError:
            return False

        if not isinstance(error_data, dict):
            return False

        return (
            error_data.get("code") in (44, 429)
            or "maximum number of requests"
            in str(error_data.get("message", "")).lower()
        )

    def _execute_http(
        self,
        method_name: str,
        endpoint: str,
        kwargs: dict[str, Any],
    ) -> http_transport.Response:
        url_val = kwargs["url"]
        keep_none = _KEEP_NONE_KEYS.get(self.service_name, frozenset())
        kw = http.filter_request_kwargs(kwargs, keep_none_keys=keep_none)
        started = time.monotonic()
        response = None
        start_observer = getattr(self, "on_http_attempt_started", None)
        if start_observer is not None:
            try:
                start_observer(self.service_name, method_name, endpoint)
            except Exception:
                self.logger.exception("HTTP attempt start observer failed")
        try:
            response = http.send_http_request(
                method_name,
                url_val,
                session=getattr(self, "session", None),
                **kw,
            )
            return response
        finally:
            observer = getattr(self, "on_http_attempt", None)
            if observer is not None:
                try:
                    observer(
                        self.service_name,
                        method_name,
                        endpoint,
                        time.monotonic() - started,
                        response.status_code if response is not None else None,
                    )
                except Exception:
                    self.logger.exception("HTTP attempt observer failed")

    def _retry_after_auth_failure(
        self,
        response: http_transport.Response,
        method: str,
        endpoint: str,
        req_kwargs: dict[str, Any],
        req_headers: dict[str, Any],
        failed_token: str,
        actual_is_mutation: bool,
        upload_positions: Sequence[tuple[http.SeekableStream, int]],
    ) -> http_transport.Response:
        if response.status_code != 401 or not self.token_refresh_callback:
            return response

        response.close()
        with self._token_lock:
            current_token = self._resolve_token(self.access_token, actual_is_mutation)
            if current_token == failed_token:
                self.logger.warning(
                    f"{self.service_name.capitalize()} request returned 401; "
                    "refreshing token and retrying."
                )
                refreshed_token = self.token_refresh_callback()
                if not refreshed_token:
                    raise ZohoTokenResponseError(
                        f"{self.service_name.capitalize()} token refresh returned an empty token."
                    )
                self.access_token = refreshed_token
                token = self._resolve_token(refreshed_token, actual_is_mutation)
            else:
                token = current_token
            req_headers["Authorization"] = f"Zoho-oauthtoken {token}"

            retry_kwargs = {**req_kwargs, "headers": req_headers}
            http.rewind_uploads(upload_positions)
            return self._execute_http(method, endpoint, retry_kwargs)

    def _retry_rate_limited(
        self,
        response: http_transport.Response,
        method: str,
        endpoint: str,
        req_kwargs: dict[str, Any],
        upload_positions: Sequence[tuple[http.SeekableStream, int]],
        max_attempts: int = 3,
    ) -> http_transport.Response:
        current_response = response
        for attempt in range(max_attempts):
            if not self._is_rate_limited(current_response):
                break
            retry_after = http.parse_retry_after(getattr(current_response, "headers", None))
            self.logger.warning(
                f"{self.service_name.capitalize()} rate limit reached (status {current_response.status_code}); "
                f"sleeping for {retry_after}s before retry (attempt {attempt + 1}/{max_attempts})..."
            )
            current_response.close()
            time.sleep(retry_after)
            http.rewind_uploads(upload_positions)
            current_response = self._execute_http(method, endpoint, req_kwargs)
        return current_response

    def _notify_request_completed(
        self,
        method: str,
        endpoint: str,
        payload_json: Any,
        response: http_transport.Response,
        stream: bool,
    ) -> None:
        if not self.on_request_completed:
            return
        try:
            response_body = None if stream else response.text
            self.on_request_completed(method, endpoint, payload_json, response.status_code, response_body)
        except Exception as e:
            self.logger.error(f"Callback on_request_completed failed: {e}")

    def request(
        self,
        method: str,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        stream: bool = False,
        override_url: str | None = None,
        is_mutation: bool | None = None,
        timeout: int | None = None
    ) -> Any:
        url = override_url if override_url else f"{self.base_url}/{endpoint}"
        if override_url:
            base = urlsplit(self.base_url)
            http.validate_https_override_url(
                override_url, {base.hostname, f"download.zoho.{self.domain}"}
            )
        actual_is_mutation = self._determine_is_mutation(method, is_mutation)

        token = self._resolve_token(self.access_token, actual_is_mutation)
        req_headers = self._build_headers(
            token=token,
            method=method,
            headers=headers,
            has_files=bool(files),
            has_data=bool(data),
        )

        logged_params = sanitize_log_params(params) if params else {}
        self.logger.info(f"Request: {method} {sanitize_log_url(url)} | Params: {logged_params}")

        req_kwargs: dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": req_headers,
            "params": params,
            "json": json,
            "data": data,
            "files": files,
            "timeout": timeout if timeout is not None else self.default_timeout,
        }
        if self.service_name in ("wd", "mail") or stream:
            req_kwargs["stream"] = stream

        upload_positions = http.capture_upload_positions(files)
        response = self._execute_http(method, endpoint, req_kwargs)

        response = self._retry_after_auth_failure(
            response=response,
            method=method,
            endpoint=endpoint,
            req_kwargs=req_kwargs,
            req_headers=req_headers,
            failed_token=token,
            actual_is_mutation=actual_is_mutation,
            upload_positions=upload_positions,
        )

        response = self._retry_rate_limited(
            response=response,
            method=method,
            endpoint=endpoint,
            req_kwargs=req_kwargs,
            upload_positions=upload_positions,
        )

        self.logger.info(f"Response: {response.status_code}")
        self._notify_request_completed(method, endpoint, json, response, stream)

        if stream:
            if response.status_code >= 400:
                try:
                    self._raise_for_status(response, endpoint=endpoint)
                finally:
                    response.close()
            return response

        self._raise_for_status(response, endpoint=endpoint)
        return http.decode_response(response)
