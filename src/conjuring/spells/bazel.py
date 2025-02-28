"""Bazel spells."""

from pathlib import Path

from invoke import Context, task

from conjuring.grimoire import run_command

SHOULD_PREFIX = True


def should_display_tasks() -> bool:
    """Check if the current directory has a Bazel module."""
    return Path("MODULE.bazel").exists()


@task
def clean(c: Context, expunge: bool = True) -> None:
    """Clean the Bazel workspace."""
    run_command(c, "bazel clean", "--expunge" if expunge else "")


@task
def sync(c: Context) -> None:
    """Sync the Bazel workspace."""
    c.run("bazel sync")


@task
def gazelle(c: Context, update: bool = False) -> None:
    """Run Gazelle."""
    run_command(c, "bazel run //:gazelle", "--update" if update else "")
