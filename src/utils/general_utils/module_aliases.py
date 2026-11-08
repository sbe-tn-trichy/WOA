"""Explicit lazy import aliases for modules moved into focused packages."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from collections.abc import Mapping, Sequence
from types import ModuleType


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, target: str) -> None:
        self.target = target
        self.canonical_spec: importlib.machinery.ModuleSpec | None = None

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        module = importlib.import_module(self.target)
        self.canonical_spec = module.__spec__
        return module

    def exec_module(self, module: ModuleType) -> None:
        # Both names must refer to one module so monkeypatches, exception types
        # and cached state keep their identity across old and new imports.
        module.__spec__ = self.canonical_spec


class _AliasFinder(importlib.abc.MetaPathFinder):
    def __init__(self) -> None:
        self.aliases: dict[str, str] = {}

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        destination = self.aliases.get(fullname)
        if destination is None:
            return None
        canonical = importlib.util.find_spec(destination)
        if canonical is None:
            raise ModuleNotFoundError(
                f"Alias {fullname!r} targets missing module {destination!r}"
            )
        return importlib.machinery.ModuleSpec(
            fullname,
            _AliasLoader(destination),
            origin="compatibility-alias",
            is_package=canonical.submodule_search_locations is not None,
        )


def register_module_aliases(aliases: Mapping[str, str]) -> None:
    """Register explicit old-to-canonical names without loading their targets."""
    if any(alias == destination for alias, destination in aliases.items()):
        raise ValueError("Module aliases must target a different canonical name")
    finder = next(
        (item for item in sys.meta_path if isinstance(item, _AliasFinder)), None
    )
    if finder is None:
        finder = _AliasFinder()
        sys.meta_path.insert(0, finder)
    for alias, destination in aliases.items():
        existing = finder.aliases.get(alias)
        if existing is not None and existing != destination:
            raise ValueError(f"Conflicting destination for module alias {alias!r}")
    finder.aliases.update(aliases)
