from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, overload

from ..base import BaseResource

if TYPE_CHECKING:
    from zoho.core_sdk.base_client import BaseZohoClient


class Folders(BaseResource):
    def __init__(self, client: BaseZohoClient, account_id: str):
        super().__init__(client, f"accounts/{account_id}/folders")
        self.account_id = account_id

    @overload
    def create(
        self,
        folder_name: str,
        parent_folder_id: str | None = None,
        *,
        params: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
    ) -> object: ...

    @overload
    def create(
        self,
        data: Mapping[str, object],
        params: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
    ) -> object: ...

    def create(self, *args: object, **kwargs: object) -> object:
        if args and isinstance(args[0], Mapping):
            data_map = args[0]
            params = args[1] if len(args) > 1 and isinstance(args[1], Mapping) else kwargs.get("params")
            files = args[2] if len(args) > 2 and isinstance(args[2], Mapping) else kwargs.get("files")
            return super().create(
                data=data_map,
                params=params if isinstance(params, Mapping) else None,
                files=files if isinstance(files, Mapping) else None,
            )
        if "data" in kwargs and isinstance(kwargs["data"], Mapping):
            params = kwargs.get("params")
            files = kwargs.get("files")
            return super().create(
                data=kwargs["data"],
                params=params if isinstance(params, Mapping) else None,
                files=files if isinstance(files, Mapping) else None,
            )
        folder_name = args[0] if args else kwargs.get("folder_name", "")
        parent_folder_id = args[1] if len(args) > 1 else kwargs.get("parent_folder_id")
        params = kwargs.get("params")
        files = kwargs.get("files")
        data: dict[str, object] = {"folderName": str(folder_name)}
        if parent_folder_id:
            data["parentFolderId"] = str(parent_folder_id)
        return super().create(
            data,
            params=params if isinstance(params, Mapping) else None,
            files=files if isinstance(files, Mapping) else None,
        )

    def rename(self, folder_id: str, new_name: str) -> object:
        data = {"folderName": new_name}
        return self.update(folder_id, data)
