from typing import Any

class ActiveInactiveMixin:
    def mark_as_active(self: Any, resource_id: str) -> dict[str, Any]:
        return self._action('POST', resource_id, 'active')

    def mark_as_inactive(self: Any, resource_id: str) -> dict[str, Any]:
        return self._action('POST', resource_id, 'inactive')

class StatusMixin:
    def mark_as_void(self: Any, resource_id: str) -> dict[str, Any]:
        return self._action('POST', resource_id, 'status/void')

    def mark_as_open(self: Any, resource_id: str) -> dict[str, Any]:
        return self._action('POST', resource_id, 'status/open')

    def mark_as_sent(self: Any, resource_id: str) -> dict[str, Any]:
        return self._action('POST', resource_id, 'status/sent')

    def mark_as_draft(self: Any, resource_id: str) -> dict[str, Any]:
        return self._action('POST', resource_id, 'status/draft')

class ApprovalMixin:
    def submit_for_approval(self: Any, resource_id: str) -> dict[str, Any]:
        return self._action('POST', resource_id, 'submit')

    def approve(self: Any, resource_id: str) -> dict[str, Any]:
        return self._action('POST', resource_id, 'approve')

class EmailMixin:
    def email(self: Any, resource_id: str, data: dict[str, Any], params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._action('POST', resource_id, 'email', data=data, params=params)

class CreditsMixin:
    def apply_credits(self: Any, resource_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._action('POST', resource_id, 'credits', data=data)
