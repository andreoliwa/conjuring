import re
from pathlib import Path
from typing import Callable

from invoke import Task

POETRY_LINE = re.compile(r"\[tool\..*poetry\]")
ShouldDisplayTasks = Callable[[], bool]

always_visible: ShouldDisplayTasks = lambda: True


def has_pre_commit_config_yaml() -> bool:
    return Path(".pre-commit-config.yaml").exists()


def is_home_dir() -> bool:
    return Path.cwd() == Path.home()


def is_git_repo() -> bool:
    """Only display tasks if the current dir is a Git repo."""
    return Path(".git").exists()


def is_poetry_project() -> bool:
    fpath = Path("pyproject.toml")
    return fpath.exists() and _has_poetry_line(fpath)


def _has_poetry_line(fpath: Path) -> bool:
    return any(re.search(POETRY_LINE, line) for line in fpath.open(encoding="utf-8"))


def display_task(task: Task, module_flag: bool) -> bool:
    if isinstance(task, MagicTask):
        # This is our custom task, let's check its visibility before the module
        return task.should_display()

    # This is a regular Invoke Task; let's check if the module should be visible or not
    return module_flag


class MagicTask(Task):
    def __init__(
        self,
        body,
        name=None,
        aliases=(),
        positional=None,
        optional=(),
        default=False,
        auto_shortflags=True,
        help=None,
        pre=None,
        post=None,
        autoprint=False,
        iterable=None,
        incrementable=None,
        should_display: ShouldDisplayTasks = always_visible,
    ):
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
