from typing import Any
from ..base import BaseResource
from .mixins import ActiveInactiveMixin

class Projects(BaseResource, ActiveInactiveMixin):
    def __init__(self, client: Any):
        super().__init__(client, 'projects')

    def clone(self, project_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._action('POST', project_id, 'clone', data=data)

class Tasks(BaseResource):
    def __init__(self, client: Any):
        super().__init__(client, 'tasks')

    def create(
        self, data: dict[str, Any] | list[dict[str, Any]],
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        """Books task creation accepts an array as well as a single task."""
        payload = data if isinstance(data, list) else self._prepare_payload(data)
        return self.client.request('POST', self.endpoint, json=payload, params=params, files=files)

class TimeEntries(BaseResource):
    def __init__(self, client: Any):
        super().__init__(client, 'projects/timeentries')

    def start_timer(self, time_entry_id: str) -> dict[str, Any]:
        return self._action('POST', time_entry_id, 'timer/start')
        
    def stop_timer(self) -> dict[str, Any]:
        return self._action('POST', None, 'timer/stop')
