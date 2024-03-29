"""Visibility predicates and a custom Invoke task that can be hidden."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from invoke import Task

from conjuring.constants import PRE_COMMIT_CONFIG_YAML, PYPROJECT_TOML

if TYPE_CHECKING:
    from collections.abc import Iterable


TOOL_POETRY_SECTION = "[tool.poetry]"
ShouldDisplayTasks = Callable[[], bool]


def always_visible() -> bool:
    """Predicate that always returns True."""
    return True


def has_pre_commit_config_yaml() -> bool:
    """Return True if the current dir has a .pre-commit-config.yaml file."""
    return Path(PRE_COMMIT_CONFIG_YAML).exists()


def is_home_dir() -> bool:
    """Return True if the current dir is the user's home dir."""
    return Path.cwd() == Path.home()


def is_git_repo() -> bool:
    """Only display tasks if the current dir is a Git repo."""
    return Path(".git").exists()


def has_pyproject_toml() -> bool:
    """Return True if the current dir has a pyproject.toml file."""
    return Path(PYPROJECT_TOML).exists()


def is_poetry_project() -> bool:
    """Return True if the current dir is a Poetry project."""
    pyproject_toml = Path(PYPROJECT_TOML)
    return pyproject_toml.exists() and TOOL_POETRY_SECTION in pyproject_toml.read_text(encoding="utf-8")


def display_task(task: Task, module_flag: bool) -> bool:  # TODO: refactor: rename to should_display_task
    """Return True if the task should be displayed."""
    if isinstance(task, MagicTask):
        # This is our custom task, let's check its visibility before the module
        return task.should_display()

    # This is a regular Invoke Task; let's check if the module should be visible or not
    return module_flag


class MagicTask(Task):
    """An Invoke task that can be hidden."""

    def __init__(  # noqa: PLR0913
        self,
        body: Callable,
        name: str | None = None,
        aliases: Iterable[str] = (),
        positional: Iterable[str] | None = None,
        optional: Iterable[str] = (),
        default: bool = False,
        auto_shortflags: bool = True,
        help: dict[str, Any] | None = None,  # noqa: A002
        pre: list[str] | str | None = None,
        post: list[str] | str | None = None,
        autoprint: bool = False,
        iterable: Iterable[str] | None = None,
        incrementable: Iterable[str] | None = None,
        should_display: ShouldDisplayTasks = always_visible,
    ) -> None:
        self.should_display: ShouldDisplayTasks = should_display
        super().__init__(
            body,
            name,
            aliases,
            positional,
            optional,
            default,
            auto_shortflags,
            help,
            pre,
            post,
            autoprint,
            iterable,
            incrementable,
        )
