from pathlib import Path
from typing import Callable

ShouldDisplayTasks = Callable[[], bool]

always_visible: ShouldDisplayTasks = lambda: True


def has_pre_commit_config_yaml() -> bool:
    return Path(".pre-commit-config.yaml").exists()


def is_home_dir() -> bool:
    return Path.cwd() == Path.home()


def is_git_repo() -> bool:
    """Only display tasks if the current dir is a Git repo."""
    return Path(".git").exists()


def has_pyproject_toml() -> bool:
    return Path("pyproject.toml").exists()
