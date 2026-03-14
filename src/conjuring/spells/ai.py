"""[Claude Code](https://claude.ai/code) and AI tooling maintenance tasks."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import typer
from invoke import Context, task

from conjuring.grimoire import ask_user_prompt, print_error, print_success, print_warning, run_command, run_stdout
from conjuring.spells.git import Git

SHOULD_PREFIX = True

OLD_STRING = (
    "    # Find all hookify.*.local.md files\n"
    "    pattern = os.path.join('.claude', 'hookify.*.local.md')\n"
    "    files = glob.glob(pattern)\n"
)

NEW_STRING = (
    "    # Find all hookify.*.local.md files (local project + global ~/.claude/)\n"
    "    pattern = os.path.join('.claude', 'hookify.*.local.md')\n"
    "    global_pattern = os.path.join(os.path.expanduser('~'), '.claude', 'hookify.*.local.md')\n"
    "    files = list(set(glob.glob(pattern) + glob.glob(global_pattern)))\n"
)


@task
def claude_patch(c: Context) -> None:
    """Patch the hookify plugin to load global ~/.claude/hookify.*.local.md rule files."""
    marketplace = (
        Path.home() / ".claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/core/config_loader.py"
    )
    cache_glob = ".claude/plugins/cache/claude-plugins-official/hookify/*/core/config_loader.py"

    targets = []
    if marketplace.exists():
        targets.append(marketplace)
    targets.extend(Path.home().glob(cache_glob))

    if not targets:
        print_error("No hookify config_loader.py files found — is the plugin installed?")
        sys.exit(1)

    for path in sorted(targets):
        text = path.read_text()
        if OLD_STRING not in text:
            print_warning(f"Already patched (or unexpected content): {path}")
            continue
        path.write_text(text.replace(OLD_STRING, NEW_STRING, 1))
        print_success(f"Patched: {path}")


@task
def iteration(c: Context) -> None:
    """Commit all changes as a numbered AI iteration (e.g. chore(ai): #3 <message>)."""
    # Guard: must not be on master or main
    git = Git(c)
    current_branch = git.current_branch()
    if current_branch in ("master", "main"):
        print_error("You should create a branch to use inv ai.iteration")
        sys.exit(1)

    # Guard: must have changes to commit
    status = run_stdout(c, "git status --porcelain")
    if not status:
        print_error("There are no changes to commit")
        sys.exit(1)

    print(status)
    # Ask for commit message
    commit_message = ask_user_prompt("Commit message:")
    if not commit_message.strip():
        print_error("Commit message cannot be empty")
        sys.exit(1)

    # Determine the base branch via git-extras config, falling back to master
    base_branch = git.default_branch() or "master"

    # Find the last "chore(ai): #<number>" commit on this branch
    log_lines = run_stdout(c, f"git log ...{base_branch} --oneline --no-merges").splitlines()
    last_number = 0
    pattern = re.compile(r"chore\(ai\):\s+#(\d+)")
    for line in log_lines:
        match = pattern.search(line)
        if match:
            last_number = int(match.group(1))
            break

    next_number = last_number + 1

    # Stage all changes
    run_command(c, "git add --all")

    # Attempt commit
    full_message = f"chore(ai): #{next_number} {commit_message}"
    result = c.run(f'git commit -m "{full_message}"', warn=True)

    if result.failed:
        # Pre-commit hooks failed — ask user whether to commit anyway
        try:
            typer.confirm("The commit has failed due to pre-commit hooks. Commit anyway?", default=True, abort=True)
        except typer.Abort:
            print_warning("Commit aborted.")
            return
        run_command(c, f'git commit --no-verify -m "{full_message}"')

    print_success(f"Committed: {full_message}")
