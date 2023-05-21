"""Reusable global Invoke tasks that can be merged with local project tasks.

Helpful docs:
- http://www.pyinvoke.org/
- http://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run
"""
from __future__ import annotations

import importlib
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from conjuring.grimoire import collection_from_python_files, magically_add_tasks

if TYPE_CHECKING:
    from collections.abc import Sequence

    from invoke import Collection

__all__ = [
    "Spellbook",
]


@dataclass
class ConjuringConfig:
    include: Sequence[str] | None
    exclude: Sequence[str] | None


class Spellbook:
    """A book with Invoke spells to cast."""

    def __init__(self) -> None:
        self.python_modules_to_import: dict[str, set[Path]] = defaultdict(set)
        self.sys_path_dirs: dict[Path, str] = {}

    def import_dirs(self, *spell_dir: str | Path) -> Spellbook:  # TODO: test
        """Import all spells from the given glob pattern."""
        for str_or_path in spell_dir:
            dir_ = Path(str_or_path).expanduser()
            if not dir_.is_dir():
                msg = f"{dir_} is not a directory"
                raise ValueError(msg)

            package = ""
            package_dir = None
            modules: set[Path] = set()
            for file in dir_.glob("*.py"):
                if file.stem == "__init__":
                    package = file.parent.name
                    package_dir = file.parent.parent
                else:
                    modules.add(file)

            if not modules:
                msg = f"No Python modules found in {dir_}"
                raise ValueError(msg)
            self.python_modules_to_import[package].update(modules)
            self.sys_path_dirs[package_dir or dir_] = package
        return self

    def cast_all(self) -> Collection:  # TODO: test
        """Load all spell modules."""
        return self._cast_chosen_spells(ConjuringConfig(include=None, exclude=None))

    def cast_only(self, *include: str) -> Collection:  # TODO: test
        """Load only the chosen spell modules by partial task name."""
        return self._cast_chosen_spells(ConjuringConfig(include=include, exclude=None))

    def cast_all_except(self, *exclude: str) -> Collection:  # TODO: test
        """Load all spell modules except the chosen ones by partial task name."""
        return self._cast_chosen_spells(ConjuringConfig(include=None, exclude=exclude))

    def _cast_chosen_spells(self, config: ConjuringConfig) -> Collection:
        """Load the chosen spell modules dynamically and add their tasks to the namespace."""
        namespace = collection_from_python_files(
            sys.modules[__name__],
            "tasks.py",
            "conjuring*.py",
            include=config.include,
            exclude=config.exclude,
        )

        conjuring_spell_dir = (Path(__file__).parent / "spells").absolute()
        self._add_tasks(
            namespace,
            sorted(conjuring_spell_dir.glob("*.py")),
            ".".join(conjuring_spell_dir.parts[-2:]),
            config,
        )

        # Add the package to PYTHONPATH so that we can import its modules
        package_count = 0
        for package_dir, package in self.sys_path_dirs.items():
            sys.path.insert(0, str(package_dir))
            package_count += 1

            if package:
                importlib.import_module(package)

        for package, python_files in self.python_modules_to_import.items():
            self._add_tasks(namespace, sorted(python_files), package, config)

        # Remove the directories added to PYTHONPATH
        for _ in range(package_count):
            sys.path.pop(0)

        return namespace

    @staticmethod
    def _add_tasks(
        namespace: Collection,
        python_files: list[Path],
        package: str,
        config: ConjuringConfig,
    ) -> None:
        for module_file in python_files:
            module_name = module_file.stem
            if module_name == "__init__":
                continue
            qualified_name = f"{package}.{module_name}" if package else module_name
            module = importlib.import_module(qualified_name)
            magically_add_tasks(namespace, module, include=config.include, exclude=config.exclude)
