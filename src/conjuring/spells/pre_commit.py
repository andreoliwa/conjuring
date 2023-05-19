from typing import Optional

from invoke import task

from conjuring.grimoire import run_command, run_stdout, run_with_fzf
from conjuring.visibility import ShouldDisplayTasks, has_pre_commit_config_yaml

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = has_pre_commit_config_yaml


def _run_garbage_collector(c):
    c.run("pre-commit gc")


def get_hook_types(commit_msg: bool, desired_hooks: Optional[list[str]] = None):
    """Prepare a list of hook types to install/uninstall."""
    hooks = ["pre-commit"]
    if desired_hooks:
        hooks.extend(desired_hooks)
    if commit_msg:
        hooks.append("commit-msg")
        hooks.append("prepare-commit-msg")
    return " ".join([f"--hook-type {h}" for h in hooks])


@task(help={"gc": "Run the garbage collector to remove unused venvs", "commit_msg": "Install commit message hooks"})
def install(c, gc=False, commit_msg=True):
    """Pre-commit install hooks."""
    if gc:
        _run_garbage_collector(c)
    c.run(f"pre-commit install {get_hook_types(commit_msg)} --install-hooks")


@task(help={"gc": "Run the garbage collector to remove unused venvs", "commit_msg": "Uninstall commit message hooks"})
def uninstall(c, gc=False, commit_msg=True):
    """Pre-commit uninstall ALL hooks."""
    if gc:
        _run_garbage_collector(c)

    installed_hooks = [hook for hook in run_stdout(c, "ls .git/hooks", dry=False).splitlines() if ".sample" not in hook]
    c.run(f"pre-commit uninstall {get_hook_types(commit_msg, installed_hooks)}")


@task(
    help={
        "hooks": "Comma-separated list of partial hook IDs (fzf will be used to match them)."
        " Use 'all', '.' or '-' to run all hooks."
    }
)
def run(c, hooks):
    """Pre-commit run all hooks or a specific one. Don't stop on failures. Needs fzf and yq."""
    split_hooks = hooks.split(",")
    chosen_hooks = []
    for special in ("all", ".", "-"):
        if special in split_hooks:
            chosen_hooks.append("")
            break
    if not chosen_hooks:
        for partial_hook in split_hooks:
            chosen_hooks.append(
                run_with_fzf(c, "yq e '.repos[].hooks[].id' .pre-commit-config.yaml", query=partial_hook, dry=False)
            )

    for chosen_hook in chosen_hooks:
        run_command(c, "pre-commit run --all-files", chosen_hook, warn=True)


@task()
def auto(c, repo="", bleed=False):
    """Autoupdate a Git hook or all hooks with the latest tag. Needs fzf and yq."""
    command = ""
    if repo:
        chosen = run_with_fzf(c, "yq e '.repos[].repo' .pre-commit-config.yaml", query=repo, dry=False)
        command = f"--repo {chosen}"
    run_command(c, "pre-commit autoupdate", "--bleeding-edge" if bleed else "", command)
