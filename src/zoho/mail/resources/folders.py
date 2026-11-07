from ..base import BaseResource
from typing import Any

class Folders(BaseResource):
    def __init__(self, client, account_id: str):
        super().__init__(client, f"accounts/{account_id}/folders")
        self.account_id = account_id

    def create(self, folder_name: str, parent_folder_id: str | None = None) -> dict[str, Any]:
        data = {"folderName": folder_name}
        if parent_folder_id:
            data["parentFolderId"] = parent_folder_id
        return super().create(data)

    def rename(self, folder_id: str, new_name: str) -> dict[str, Any]:
        data = {"folderName": new_name}
        return self.update(folder_id, data)
