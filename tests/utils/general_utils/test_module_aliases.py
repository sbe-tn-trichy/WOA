"""Failure and laziness contracts for explicit compatibility module aliases."""

from __future__ import annotations

import importlib
import sys

import pytest

from utils.general_utils.module_aliases import register_module_aliases


@pytest.fixture(autouse=True)
def isolated_alias_registry(monkeypatch):
    # The API installs a finder lazily. Keep test-only registrations out of the
    # process registry used by real package compatibility imports.
    monkeypatch.setattr(sys, "meta_path", [
        finder for finder in sys.meta_path
        if type(finder).__module__ != "utils.general_utils.module_aliases"
    ])


def test_registration_does_not_import_target() -> None:
    alias = "_woa_missing_target_alias"
    register_module_aliases({alias: "_woa_missing_target"})
    assert "_woa_missing_target" not in sys.modules
    with pytest.raises(ModuleNotFoundError, match="targets missing module"):
        importlib.import_module(alias)


def test_self_alias_is_rejected() -> None:
    with pytest.raises(ValueError, match="different canonical name"):
        register_module_aliases({"_woa_alias": "_woa_alias"})


def test_conflicting_registration_keeps_original_destination() -> None:
    register_module_aliases({"_woa_alias": "decimal"})
    register_module_aliases({"_woa_alias": "decimal"})
    with pytest.raises(ValueError, match="Conflicting destination"):
        register_module_aliases({"_woa_alias": "fractions"})
    spec = importlib.util.find_spec("_woa_alias")
    assert spec.loader.target == "decimal"
