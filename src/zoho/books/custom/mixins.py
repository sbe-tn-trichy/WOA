from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class _ActionProtocol(Protocol):
    def _action(
        self,
        method: str,
        resource_id: str | None,
        action: str,
        data: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object: ...


class ActiveInactiveMixin:
    def mark_as_active(self: _ActionProtocol, resource_id: str) -> object:
        return self._action("POST", resource_id, "active")

    def mark_as_inactive(self: _ActionProtocol, resource_id: str) -> object:
        return self._action("POST", resource_id, "inactive")


class StatusMixin:
    def mark_as_void(self: _ActionProtocol, resource_id: str) -> object:
        return self._action("POST", resource_id, "status/void")

    def mark_as_open(self: _ActionProtocol, resource_id: str) -> object:
        return self._action("POST", resource_id, "status/open")

    def mark_as_sent(self: _ActionProtocol, resource_id: str) -> object:
        return self._action("POST", resource_id, "status/sent")

    def mark_as_draft(self: _ActionProtocol, resource_id: str) -> object:
        return self._action("POST", resource_id, "status/draft")


class ApprovalMixin:
    def submit_for_approval(self: _ActionProtocol, resource_id: str) -> object:
        return self._action("POST", resource_id, "submit")

    def approve(self: _ActionProtocol, resource_id: str) -> object:
        return self._action("POST", resource_id, "approve")


class EmailMixin:
    def email(
        self: _ActionProtocol,
        resource_id: str,
        data: Mapping[str, object],
        params: Mapping[str, object] | None = None,
    ) -> object:
        return self._action(
            "POST",
            resource_id,
            "email",
            data=dict(data),
            params=dict(params) if params else None,
        )


class CreditsMixin:
    def apply_credits(
        self: _ActionProtocol,
        resource_id: str,
        data: Mapping[str, object],
    ) -> object:
        return self._action("POST", resource_id, "credits", data=dict(data))
