from __future__ import annotations

import logging
import mimetypes
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from utils.http_utils.http import write_response_to_file
from zoho.core_sdk.security import resolve_output_path, sanitize_filename
from ..base import BaseResource

if TYPE_CHECKING:
    from ..client import ZohoWorkdriveAPI

# Logger setup

app_logger = logging.getLogger("zoho_wd.app")
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SENSITIVE_PARAM_KEYS = frozenset({"token", "secret", "password", "key", "authorization", "auth"})


def _redact_params(params: Mapping[str, object] | None) -> dict[str, object] | None:
    if params is None:
        return None
    return {
        k: ("<redacted>" if any(s in k.lower() for s in _SENSITIVE_PARAM_KEYS) else v)
        for k, v in params.items()
    }


class Files(BaseResource):
    """Resource class for Zoho Workdrive Files operations."""

    def __init__(self, client: ZohoWorkdriveAPI):
        super().__init__(client, "files")
        self.client: ZohoWorkdriveAPI = client

    def list_files(self, folder_id: str, params: Mapping[str, object] | None = None) -> object:
        """List files and folders within a specific folder."""
        app_logger.info(f"Listing files in folder: {folder_id} with params: {_redact_params(params)}")
        endpoint = f"files/{folder_id}/files"
        return self.client.request('GET', endpoint, params=params)

    def list_all_files(self, folder_id: str, params: Mapping[str, object] | None = None) -> list[dict[str, object]]:
        """Fetch all files and folders across all pages using limit/offset pagination."""
        all_data: list[dict[str, object]] = []
        page_limit = 100 # WorkDrive limit is often 50 or 100
        offset = 0
        base_params = dict(params or {})
        while True:
            current_params: dict[str, object] = {**base_params, "page[limit]": page_limit, "page[offset]": offset}
            res = self.list_files(folder_id, params=current_params)
            raw_data = res.get('data', []) if isinstance(res, dict) else []
            data = [d for d in raw_data if isinstance(d, dict)] if isinstance(raw_data, list) else []
            all_data.extend(data)

            # Check if there are more pages
            if len(data) < page_limit:
                break

            offset += page_limit
        return all_data

    def download(self, file_id: str, save_path: str | Path, source_folder_id: str | None = None) -> None:
        """Download a file and save it to the specified path."""
        resolved_save_path = resolve_output_path(str(save_path))
        app_logger.info(f"Downloading file {file_id} to {resolved_save_path}")
        download_url = f"https://download.zoho.{self.client.domain}/v1/workdrive/download/{file_id}"
        response = self.client.request('GET', '', stream=True, override_url=download_url)
        write_response_to_file(response, resolved_save_path)
        app_logger.info(f"Successfully downloaded file {file_id}")

    def _safe_download_name(self, name: str | None, fallback: str) -> str:
        """Return a filesystem-safe filename while keeping it readable."""
        return sanitize_filename(name, fallback=fallback)

    def _is_folder_item(self, item: Mapping[str, object]) -> bool:
        """Detect folder records across the shapes returned by WorkDrive APIs."""
        raw_attrs = item.get("attributes")
        attrs = raw_attrs if isinstance(raw_attrs, dict) else {}
        return bool(
            attrs.get("is_folder")
            or item.get("type") == "folders"
            or attrs.get("type") == "folder"
            or attrs.get("resource_type") == "folder"
        )

    def _item_name(self, item: Mapping[str, object]) -> str:
        raw_attrs = item.get("attributes")
        attrs = raw_attrs if isinstance(raw_attrs, dict) else {}
        return str(attrs.get("name") or item.get("name") or item.get("id") or "unnamed")

    def _next_available_download_path(self, path: Path, reserved_paths: set[Path]) -> Path:
        """Avoid duplicate source names in one run while keeping reruns idempotent."""
        if path not in reserved_paths:
            reserved_paths.add(path)
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1
        while True:
            candidate = parent / f"{stem} ({counter}){suffix}"
            if candidate not in reserved_paths:
                reserved_paths.add(candidate)
                return candidate
            counter += 1

    def download_folder(
        self,
        folder_id: str,
        destination: os.PathLike[str] | str,
        *,
        dry_run: bool = False,
    ) -> list[Path]:
        """Recursively download all files from a Zoho WorkDrive folder."""
        dest_path = Path(resolve_output_path(str(destination)))
        root = dest_path.expanduser().resolve()

        downloaded: list[Path] = []
        reserved_paths: set[Path] = set()

        def walk(current_folder_id: str, current_local_dir: Path) -> None:
            app_logger.info(f"Listing WorkDrive folder {current_folder_id}")
            items = self.list_all_files(current_folder_id)
            current_local_dir.mkdir(parents=True, exist_ok=True)

            for item in items:
                item_id = str(item.get("id") or "")
                if not item_id:
                    app_logger.warning(f"Skipping WorkDrive item without an id: {item}")
                    continue

                safe_name = self._safe_download_name(self._item_name(item), item_id)
                local_path = current_local_dir / safe_name

                if self._is_folder_item(item):
                    walk(item_id, local_path)
                    continue

                target_path = self._next_available_download_path(local_path, reserved_paths)
                downloaded.append(target_path)
                if dry_run:
                    app_logger.info(f"Would download {item_id} -> {target_path}")
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)
                app_logger.info(f"Downloading {item_id} -> {target_path}")
                self.download(item_id, str(target_path), source_folder_id=current_folder_id)

        walk(folder_id, root)
        return downloaded

    def move(self, file_id: str, destination_folder_id: str) -> object:
        """Move a file to a new folder."""
        app_logger.info(f"Moving file {file_id} to folder {destination_folder_id}")
        payload = {"data": {"attributes": {"parent_id": destination_folder_id}, "type": "files"}}
        return self._action('PATCH', file_id, '', data=payload)

    def create_folder(self, name: str, parent_id: str) -> object:
        """Create a new folder in WorkDrive."""
        app_logger.info(f"Creating folder '{name}' in parent '{parent_id}'")
        payload = {"data": {"attributes": {"name": name, "parent_id": parent_id}, "type": "files"}}
        return self.client.request('POST', 'files', json=payload)

    def delete(self, resource_id: str) -> object:
        """Move a file or folder to the trash."""
        app_logger.info(f"Deleting (trashing) resource: {resource_id}")
        return self.client.request('DELETE', f"files/{resource_id}")

    def search(self, name: str, parent_id: str | None = None, resource_type: str | None = "folder") -> list[dict[str, object]]:
        """Search for files and folders using organization records search."""
        team_id = self.client.get_team_id()
        endpoint = f"organization/{team_id}/records"
        params: dict[str, object] = {"search[all]": name}
        if parent_id:
            params["filter[parentId]"] = parent_id
        if resource_type:
            params["filter[type]"] = resource_type

        res = self.client.request('GET', endpoint, params=params)
        raw_data = res.get('data', []) if isinstance(res, dict) else []
        return [d for d in raw_data if isinstance(d, dict)] if isinstance(raw_data, list) else []

    def upload(self, folder_id: str, file_path: str | Path, file_name: str | None = None) -> object:
        """Upload a file to WorkDrive."""
        str_path = str(file_path)
        if not os.path.exists(str_path):
            raise FileNotFoundError(f"File not found: {str_path}")
        name = file_name or os.path.basename(str_path)
        app_logger.info(f"Uploading file '{name}' to folder '{folder_id}'")
        content_type, _ = mimetypes.guess_type(str_path)
        if not content_type:
            content_type = 'application/octet-stream'
        with open(str_path, 'rb') as f:
            return self.client.request('POST', 'upload', params={"parent_id": folder_id}, files={'content': (name, f, content_type)})

    def get_base_name(self, name: str) -> str:
        """Extract base name from timestamped or numbered duplicates."""
        match = re.match(r"^(.*?)(?:\s+\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2}:\d{3}|\s+\(\d+\))?$", name)
        return match.group(1).strip() if match else name

    def merge_folders(self, source_id: str, target_id: str, folder_name: str) -> None:
        """Recursively move contents from source folder to target folder."""
        app_logger.info(f"Merging contents of '{folder_name}' ({source_id}) -> ({target_id})")

        source_items = self.list_all_files(source_id)
        target_items = self.list_all_files(target_id)

        target_map: dict[str, dict[str, object]] = {}
        for item in target_items:
            attrs = item.get('attributes')
            if isinstance(attrs, dict) and 'name' in attrs:
                target_map[str(attrs['name'])] = item

        for s_item in source_items:
            s_attrs = s_item.get('attributes')
            if not isinstance(s_attrs, dict):
                continue
            s_name = str(s_attrs.get('name', ''))
            s_id = str(s_item.get('id', ''))
            is_folder = bool(s_attrs.get('is_folder', False))

            if s_name in target_map:
                t_item = target_map[s_name]
                t_attrs = t_item.get('attributes')
                t_id = str(t_item.get('id', ''))
                if is_folder and isinstance(t_attrs, dict) and t_attrs.get('is_folder', False):
                    # Recursive merge for sub-folders
                    self.merge_folders(s_id, t_id, s_name)
                else:
                    app_logger.warning(f"Collision for '{s_name}' in '{folder_name}': Skipping move.")
            else:
                try:
                    self.move(s_id, target_id)
                except Exception as e:
                    app_logger.error(f"Failed to move '{s_name}' during merge: {e}")

    def cleanup_duplicates(self, parent_id: str, recursive: bool = True) -> None:
        """Scan a folder for timestamped duplicates and merge them into the primary folders."""
        app_logger.info(f"Scanning for duplicates in folder: {parent_id} (recursive={recursive})")
        items = self.list_all_files(parent_id)

        groups: dict[str, list[dict[str, object]]] = {}
        for item in items:
            attrs = item.get('attributes')
            if not isinstance(attrs, dict):
                continue
            name = str(attrs.get('name', ''))
            if not attrs.get('is_folder', False):
                continue

            base_name = self.get_base_name(name)
            groups.setdefault(base_name, []).append(item)

        for base_name, folder_list in groups.items():
            if len(folder_list) <= 1:
                continue

            app_logger.info(f"Found duplicates for base name: '{base_name}'")

            target_folder: dict[str, object] | None = None
            duplicates: list[dict[str, object]] = []
            for f in folder_list:
                f_attrs = f.get('attributes')
                if isinstance(f_attrs, dict) and f_attrs.get('name') == base_name:
                    target_folder = f
                else:
                    duplicates.append(f)

            if not target_folder:
                target_folder = duplicates.pop(0)

            target_folder_id = str(target_folder.get('id', ''))
            for dup in duplicates:
                dup_attrs = dup.get('attributes')
                dup_id = str(dup.get('id', ''))
                dup_name = str(dup_attrs.get('name', '')) if isinstance(dup_attrs, dict) else ''
                if recursive:
                    self.merge_folders(dup_id, target_folder_id, dup_name)
                else:
                    # Non-recursive: just move top-level items
                    dup_items = self.list_all_files(dup_id)
                    for item in dup_items:
                        item_id = str(item.get('id', ''))
                        if item_id:
                            try:
                                self.move(item_id, target_folder_id)
                            except Exception as e:
                                app_logger.error(f"Failed to move '{item_id}': {e}")

                # Attempt to delete the empty duplicate folder
                try:
                    self.delete(dup_id)
                    app_logger.info(f"Successfully deleted duplicate folder: {dup_name}")
                except Exception as e:
                    app_logger.error(f"Failed to delete empty duplicate folder {dup_name}: {e}")
