from invoke import task

from conjuring.grimoire import run_command, run_with_fzf
from conjuring.visibility import ShouldDisplayTasks, has_pre_commit_config_yaml

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = has_pre_commit_config_yaml


def _run_garbage_collector(c):
    c.run("pre-commit gc")


def get_hook_types(commit_msg: bool):
    """Prepare a list of hook types to install/uninstall."""
    hooks = ["pre-commit"]
    if commit_msg:
        hooks.append("commit-msg")
    return " ".join([f"--hook-type {h}" for h in hooks])


@task(help={"gc": "Run the garbage collector to remove unused venvs", "commit_msg": "Install the commit-msg hook"})
def install(c, gc=False, commit_msg=True):
    """Pre-commit install scripts and hooks."""
    if gc:
        _run_garbage_collector(c)
    c.run(f"pre-commit install {get_hook_types(commit_msg)} --install-hooks")


@task(help={"gc": "Run the garbage collector to remove unused venvs", "commit_msg": "Install the commit-msg hook"})
def uninstall(c, gc=False, commit_msg=True):
    """Pre-commit uninstall scripts and hooks."""
    if gc:
        _run_garbage_collector(c)
    c.run(f"pre-commit uninstall {get_hook_types(commit_msg)}")


@task(help={"hook": "Comma-separated list of partial hook IDs (fzf will be used to match partial IDs)."})
def run(c, hook=""):
    """Pre-commit run all hooks or a specific one. Needs fzf and yq."""
    all_hooks = hook.split(",") if "," in hook else [hook]
    chosen_hooks = []
    for partial_hook in all_hooks:
        chosen_hooks.append(
            run_with_fzf(c, "yq e '.repos[].hooks[].id' .pre-commit-config.yaml", query=partial_hook) if hook else ""
        )

    for chosen_hook in chosen_hooks:
        c.run(f"pre-commit run --all-files {chosen_hook}")


@task()
def auto(c, repo="", bleed=False):
    """Autoupdate a Git hook or all hooks with the latest tag. Needs fzf and yq."""
    command = ""
    if repo:
        chosen = run_with_fzf(c, "yq e '.repos[].repo' .pre-commit-config.yaml", query=repo, dry=False)
        command = f"--repo {chosen}"
    run_command(c, "pre-commit autoupdate", "--bleeding-edge" if bleed else "", command)
