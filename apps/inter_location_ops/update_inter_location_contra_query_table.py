"""Compatibility command for inter-location Query Table update; prefer the manager."""

from __future__ import annotations
import importlib

from collections.abc import Sequence

if __package__:
    from . import _bootstrap
    from .manage_inter_location_contra_query_table import main as _manage
else:
    importlib.import_module("_bootstrap")
    _manage = importlib.import_module("manage_inter_location_contra_query_table").main


from workflows.runtime.config import Config


def main(argv: Sequence[str] | None = None) -> int:
    """Retain the historical command defaults using the shared manager."""
    return _manage(argv, default_view_id=Config.INTER_LOCATION_CONTRA_VIEW_ID)


if __name__ == "__main__":
    raise SystemExit(main())
