from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence

from zoho.core_sdk.base_client import BaseZohoClient
from .resources.accounts import Accounts
from .resources.folders import Folders
from .resources.messages import Messages


class ZohoMailAPI(BaseZohoClient):
    """
    Main Zoho Mail API Client.
    """
    def __init__(
        self,
        access_token: str,
        domain: str = "in",
        token_refresh_callback: Callable[[BaseZohoClient], None] | Callable[[], str] | None = None,
    ):
        """
        Initialize the Zoho Mail API client.
        """
        base_url = f"https://mail.zoho.{domain}/api"
        super().__init__(
            access_token=access_token,
            domain=domain,
            base_url=base_url,
            service_name="mail",
            token_refresh_callback=token_refresh_callback,
        )
        # Global resources
        self.accounts = Accounts(self)

    def account(self, account_id: str) -> AccountScope:
        """
        Returns a helper object to access account-specific resources.
        """
        return AccountScope(self, account_id)

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
        """
        Internal HTTP request handler with logging.
        """
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


class AccountScope:
    def __init__(self, client: BaseZohoClient, acc_id: str):
        self.folders = Folders(client, acc_id)
        self.messages = Messages(client, acc_id)
