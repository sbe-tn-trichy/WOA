from typing import Any
from zoho.inventory.base import BaseResource

class Bins(BaseResource):
    """Resource class for Zoho Inventory Bins operations."""
    def __init__(self, client: Any):
        super().__init__(client, 'bins')
