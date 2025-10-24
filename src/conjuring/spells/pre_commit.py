"""[pre-commit](https://pre-commit.com/): install, uninstall, run/autoupdate selected hooks."""

from __future__ import annotations

import itertools
from pathlib import Path

from invoke import Context, task

from conjuring.constants import PRE_COMMIT_CONFIG_YAML
from conjuring.grimoire import print_success, run_command, run_stdout, run_with_fzf
from conjuring.visibility import ShouldDisplayTasks, has_pre_commit_config_yaml

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = has_pre_commit_config_yaml


def _run_garbage_collector(c: Context) -> None:
    # TODO: prek doesn't have a "gc" command yet: https://prek.j178.dev/todo/
    c.run("pre-commit gc")


def _patch_pre_commit_configs(before: list[str]) -> None:
    """Patch the pre-commit config to include other files before the current one."""
    expanded_before: list[Path] = list(itertools.chain.from_iterable(list(Path().glob(b)) for b in before))
    print_success("Patching files with ", str(expanded_before))

    for installed_hook in sorted(
        hook_file for hook_file in Path(".git/hooks").glob("*") if hook_file.suffix != ".sample"
    ):
        new_lines = []
        for old_line in installed_hook.read_text().splitlines():
            if "ARGS" not in old_line:
                new_lines.append(old_line)
                continue

            for index, before_file in enumerate(expanded_before):
                new_line = old_line.replace("ARGS", f"CONJURING_BEFORE_{index}").replace("exec ", "")
                if "ARGS=" in old_line:
                    new_line = new_line.replace(PRE_COMMIT_CONFIG_YAML, str(before_file))
                new_lines.append(new_line)

            new_lines.append(old_line)
        print_success(f"  {installed_hook} patched")
        installed_hook.write_text("\n".join(new_lines))


def get_hook_types(commit_msg: bool, desired_hooks: list[str] | None = None) -> str:
    """Prepare a list of hook types to install/uninstall."""
    hooks = ["pre-commit"]
    if desired_hooks:
        hooks.extend(desired_hooks)
    if commit_msg:
        hooks.append("commit-msg")
        hooks.append("prepare-commit-msg")
    return " ".join([f"--hook-type {h}" for h in hooks])


@task(
    help={
        "gc": "Run the garbage collector to remove unused venvs",
        "commit_msg": "Install commit message hooks",
        "before": "Config files to run before the current one.",
    },
    iterable=["before"],
)
def install(c: Context, before: list[str], gc: bool = False, commit_msg: bool = True) -> None:
    """Install pre-commit with prek."""
    if gc:
        _run_garbage_collector(c)
    c.run(f"prek install {get_hook_types(commit_msg)} --install-hooks")
    if before:
        _patch_pre_commit_configs(before)


@task(help={"gc": "Run the garbage collector to remove unused venvs", "commit_msg": "Uninstall commit message hooks"})
def uninstall(c: Context, gc: bool = False, commit_msg: bool = True) -> None:
    """Uninstall ALL pre-commit hooks with prek."""
    if gc:
        _run_garbage_collector(c)

    installed_hooks = [
        git_hook
        for git_hook in run_stdout(c, "ls .git/hooks", dry=False).splitlines()
        if ".sample" not in git_hook and ".legacy" not in git_hook
    ]
    c.run(f"prek uninstall {get_hook_types(commit_msg, installed_hooks)}")


@task(
    help={
        "hooks": "Comma-separated list of partial hook IDs (fzf will be used to match them)."
        " Use 'all', '.' or '-' to run all hooks.",
    },
)
def run(c: Context, hooks: str) -> None:
    """Run all pre-commit hooks or a specific one using prek. Don't stop on failures. Needs fzf and yq."""
    split_hooks = hooks.split(",")
    chosen_hooks = []
    for special in ("all", ".", "-"):
        if special in split_hooks:
            chosen_hooks.append("")
            break
    if not chosen_hooks:
        chosen_hooks = [
            run_with_fzf(
                c,
                "yq e '.repos[].hooks[].id' .pre-commit-config.yaml | sort -u",
                query=partial_hook,
                dry=False,
            )
            for partial_hook in split_hooks
        ]

    for chosen_hook in chosen_hooks:
        run_command(c, "prek run --all-files", chosen_hook, warn=True)


@task()
def auto(c: Context, repo: str = "", bleed: bool = False) -> None:
    """Autoupdate a Git hook or all hooks with the latest tag. Needs fzf and yq."""
    command = ""
    if repo:
        chosen = run_with_fzf(c, "yq e '.repos[].repo' .pre-commit-config.yaml", query=repo, dry=False)
        command = f"--repo {chosen}"
    run_command(c, "prek auto-update", "--bleeding-edge" if bleed else "", command)
