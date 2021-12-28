from pathlib import Path

from invoke import task

from conjuring.grimoire import run_with_fzf, run_command
from conjuring.visibility import ShouldDisplayTasks, has_pre_commit_config_yaml

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = has_pre_commit_config_yaml

GIT_HOOKS = "-t pre-commit -t commit-msg"


def _run_garbage_collector(c):
    c.run("pre-commit gc")


@task(help={"gc": "Run the garbage collector to remove unused venvs"})
def install(c, gc=False):
    """Pre-commit install scripts and hooks."""
    if gc:
        _run_garbage_collector(c)
    c.run(f"pre-commit install {GIT_HOOKS} --install-hooks")


@task(help={"gc": "Run the garbage collector to remove unused venvs"})
def uninstall(c, gc=False):
    """Pre-commit uninstall scripts and hooks."""
    if gc:
        _run_garbage_collector(c)
    c.run(f"pre-commit uninstall {GIT_HOOKS}")


@task
def run(c, hook=""):
    """Pre-commit run all hooks or a specific one."""
    chosen_hook = run_with_fzf(c, "yq e '.repos[].hooks[].id' .pre-commit-config.yaml", query=hook) if hook else ""
    c.run(f"pre-commit run --all-files {chosen_hook}")


@task()
def auto(c, repo="", bleed=False):
    """Autoupdate a Git hook or all hooks with the latest tag."""
    command = ""
    if repo:
        chosen = run_with_fzf(c, "yq e '.repos[].repo' .pre-commit-config.yaml", query=repo, dry=False)
        command = f"--repo {chosen}"
    run_command(c, "pre-commit autoupdate", "--bleeding-edge" if bleed else "", command)
