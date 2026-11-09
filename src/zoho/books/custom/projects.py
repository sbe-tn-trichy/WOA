from __future__ import annotations

from collections.abc import Mapping, Sequence

from zoho.core_sdk.base_client import BaseZohoClient
from ..base import BaseResource
from .mixins import ActiveInactiveMixin


class Projects(BaseResource, ActiveInactiveMixin):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "projects")

    def clone(
        self, project_id: str, data: Mapping[str, object]
    ) -> object:
        return self._action("POST", project_id, "clone", data=dict(data))


class Tasks(BaseResource):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "tasks")

    def create(
        self,
        data: Mapping[str, object] | Sequence[Mapping[str, object]],
        params: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
    ) -> object:
        """Books task creation accepts an array as well as a single task."""
        payload: Mapping[str, object] | Sequence[object] = (
            self._prepare_payload(dict(data))
            if isinstance(data, Mapping)
            else list(data)
        )
        return self.client.request(
            "POST",
            self.endpoint,
            json=payload,
            params=dict(params) if params else None,
            files=dict(files) if files else None,
        )


class TimeEntries(BaseResource):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "projects/timeentries")

    def start_timer(self, time_entry_id: str) -> object:
        return self._action("POST", time_entry_id, "timer/start")

    def stop_timer(self) -> object:
        return self._action("POST", None, "timer/stop")
