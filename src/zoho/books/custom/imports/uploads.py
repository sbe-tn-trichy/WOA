"""Upload and confirmation endpoints observed in the Books import flow."""
from pathlib import Path
from typing import Literal

from zoho.books.base import BaseResource
from zoho.core_sdk.base_client import BaseZohoClient


class Imports(BaseResource):
    """Stage import files and explicitly confirm a reviewed staged import."""

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "import")

    def confirm(self, import_id: str, *, is_new_flow: bool = False) -> object:
        """Confirm a staged import with PUT /import/{import_id}.

        This can change live records. Call only after reviewing the uploaded
        file, organization, duplicate handling and column mappings. The raw
        response is returned; verify saved records before reporting completion.
        This browser-observed confirmation route was verified with OAuth.
        """
        if not isinstance(import_id, str) or not import_id.isascii() or not import_id.isdigit():
            raise ValueError("import_id must be a nonempty ASCII numeric string")
        if type(is_new_flow) is not bool:
            raise ValueError("is_new_flow must be a boolean")
        organization_id = getattr(self.client, "organization_id", None)
        if not isinstance(organization_id, str) or not organization_id.strip():
            raise ValueError("client organization_id is required for import confirmation")
        return self.client.request(
            "PUT", f"import/{import_id}",
            # Books rejects organization_id duplicated between query and form.
            params={"is_new_flow": str(is_new_flow).lower(), "organization_id": organization_id},
            is_mutation=True,
        )

    def upload_file(
        self,
        file_path: str | Path,
        *,
        entity: str,
        duplicate_handling: Literal["overwrite", "skip", "create_new"],
        charencoding: str = "UTF-8",
        delimiter: str = ",",
        is_new_flow: bool = False,
    ) -> object:
        """Upload a nonempty CSV using OAuth and the client's organization.

        This browser-observed route may be unavailable through the public OAuth
        API. The raw response is returned; upload success does not establish that
        any records were imported. No mapping or import-commit request is sent.
        """
        if not isinstance(entity, str) or not entity.strip():
            raise ValueError("entity must be a nonempty Books entity name")
        if duplicate_handling not in ("overwrite", "skip", "create_new"):
            raise ValueError("duplicate_handling must be overwrite, skip, or create_new")
        if not isinstance(charencoding, str) or not charencoding.strip():
            raise ValueError("charencoding must be nonempty")
        if not isinstance(delimiter, str) or len(delimiter) != 1 or delimiter in "\r\n":
            raise ValueError("delimiter must be one non-newline character")
        if type(is_new_flow) is not bool:
            raise ValueError("is_new_flow must be a boolean")
        organization_id = getattr(self.client, "organization_id", None)
        if not isinstance(organization_id, str) or not organization_id.strip():
            raise ValueError("client organization_id is required for import upload")
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Import CSV not found: {path}")
        if path.suffix.lower() != ".csv" or path.stat().st_size == 0:
            raise ValueError("Import file must be a nonempty .csv file")
        with path.open("rb") as handle:
            return self.client.request(
                "POST", "import/uploadfile",
                params={"is_new_flow": str(is_new_flow).lower()},
                data={
                    "charencoding": charencoding,
                    "entity": entity,
                    "duplicate_handling": duplicate_handling,
                    "delimiter": delimiter,
                    "organization_id": organization_id,
                },
                files={"importfile": (path.name, handle, "text/csv")},
            )
