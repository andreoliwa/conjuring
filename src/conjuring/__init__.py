"""Reusable global Invoke tasks that can be merged with local project tasks.

Helpful docs:
- http://www.pyinvoke.org/
- http://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run
"""
import importlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from invoke import Collection

from conjuring.grimoire import collection_from_python_files, magically_add_tasks

__all__ = [
    "cast_all_spells",
    "cast_all_spells_except",
    "cast_only_spells",
]


def cast_all_spells() -> Collection:  # TODO: test
    """Load all spell modules."""
    return _cast_chosen_spells(include=None, exclude=None)


def cast_only_spells(*include: str) -> Collection:  # TODO: test
    """Load only the chosen spell modules by partial task name."""
    return _cast_chosen_spells(include=include, exclude=None)


def cast_all_spells_except(*exclude: str) -> Collection:  # TODO: test
    """Load all spell modules except the chosen ones by partial task name."""
    return _cast_chosen_spells(include=None, exclude=exclude)


def _cast_chosen_spells(*, include: Optional[Sequence[str]], exclude: Optional[Sequence[str]]) -> Collection:
    """Load the chosen spell modules dynamically and add their tasks to the namespace."""
    namespace = collection_from_python_files(
        sys.modules[__name__],
        "tasks.py",
        "conjuring*.py",
        include=include,
        exclude=exclude,
    )

    spell_dir = (Path(__file__).parent / "spells").absolute()
    parent_modules = ".".join(spell_dir.parts[-2:])
    for module_file in spell_dir.glob("*.py"):
        module_name = module_file.stem
        if module_name == "__init__":
            continue
        module = importlib.import_module(f"{parent_modules}.{module_name}")
        magically_add_tasks(namespace, module, include=include, exclude=exclude)

    return namespace
