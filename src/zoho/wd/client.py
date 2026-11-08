import logging
import os
from typing import Any
from zoho.core_sdk.base_client import BaseZohoClient
from .exceptions import ZohoWorkdriveError
from .resources.files import Files

class ZohoWorkdriveAPI(BaseZohoClient):
    """
    Main Zoho Workdrive API Client.
    """
    def __init__(
        self,
        access_token: str,
        domain: str = "in",
        team_id: str | None = None,
        token_refresh_callback: Any | None = None
    ):
        """
        Initialize the Zoho Workdrive API client.
        """
        base_url = f"https://www.zohoapis.{domain or 'in'}/workdrive/api/v1"
        super().__init__(
            access_token=access_token,
            domain=domain or "in",
            base_url=base_url,
            service_name="wd",
            token_refresh_callback=token_refresh_callback
        )
        self._team_id = team_id
        self.files = Files(self)

    def get_team_id(self) -> str:
        """Fetch the team ID (organization ID) for the current user."""
        app_logger = logging.getLogger("zoho.wd.app")
        if not self._team_id:
            app_logger.info("WORKDRIVE_TEAM_ID not provided, fetching from API...")
            res = self.request('GET', 'users/me')
            attrs = res.get('data', {}).get('attributes', {})
            # Try both team_id and preferred_team_id
            self._team_id = attrs.get('team_id') or attrs.get('preferred_team_id')
            
            if not self._team_id:
                app_logger.error("Could not determine WorkDrive Team ID")
                raise ZohoWorkdriveError("Could not determine WorkDrive Team ID")
                
        return self._team_id

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
        timeout: int | None = None,
    ) -> Any:
        """
        Internal HTTP request handler.
        """
        if isinstance(files, bool):
            import warnings
            from collections.abc import Mapping

            warnings.warn(
                "Positional arguments (stream, override_url, files) to ZohoWorkdriveAPI.request "
                "are deprecated; use keyword arguments or canonical BaseZohoClient order (files, stream, override_url).",
                DeprecationWarning,
                stacklevel=2,
            )
            legacy_stream = files
            legacy_override_url = stream if isinstance(stream, str) else None
            legacy_files = override_url if isinstance(override_url, Mapping) else None
            stream = legacy_stream
            override_url = legacy_override_url
            files = legacy_files

        return super().request(
            method=method,
            endpoint=endpoint,
            json=json,
            data=data,
            params=params,
            headers=headers,
            files=files,
            stream=stream,
            override_url=override_url,
            is_mutation=is_mutation,
            timeout=timeout,
        )
