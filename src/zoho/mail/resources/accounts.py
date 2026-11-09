from __future__ import annotations

from typing import TYPE_CHECKING
from ..base import BaseResource

if TYPE_CHECKING:
    from zoho.core_sdk.base_client import BaseZohoClient


class Accounts(BaseResource):
    def __init__(self, client: BaseZohoClient):
        super().__init__(client, "accounts")
