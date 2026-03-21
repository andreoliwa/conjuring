"""[Claude Code](https://claude.ai/code) and AI tooling maintenance tasks."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import typer
from invoke import Context, task

from conjuring.grimoire import print_error, print_success, print_warning, run_command, run_stdout
from conjuring.spells.git import Git

SHOULD_PREFIX = True

CHORE_AI_PATTERN = re.compile(r"chore\(ai\):\s+(\d+)")


def _ai_log_lines(c: Context, base_branch: str) -> list[str]:
    """Return commit log lines for the current branch since base_branch."""
    return run_stdout(c, f"git log {base_branch}..HEAD --oneline --no-merges").splitlines()


def _count_ai_iterations(log_lines: list[str]) -> int:
    """Return the highest chore(ai) iteration number found in log lines."""
    last_number = 0
    for line in log_lines:
        match = CHORE_AI_PATTERN.search(line)
        if match:
            last_number = max(last_number, int(match.group(1)))
    return last_number


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
def iteration(c: Context, message: str = "", push: bool = False) -> None:
    """Commit all changes as a numbered AI iteration (e.g. chore(ai): 3. <message>)."""
    git = Git(c)
    git.guard_not_default_branch()

    # Guard: must have changes to commit
    status = run_stdout(c, "git status --porcelain")
    if not status:
        print_error("There are no changes to commit")
        raise SystemExit(1)

    base_branch = git.resolve_base_ref(exit_on_failure=True)
    log_lines = _ai_log_lines(c, base_branch)
    next_number = _count_ai_iterations(log_lines) + 1
    commit_msg = f"chore(ai): {next_number}. {message}" if message else f"chore(ai): {next_number}. "

    # Stage all changes
    run_command(c, "git add --all")

    # Open editor when no message is provided, so the user can describe the iteration.
    # When a message is given, commit directly without the editor.
    edit_flag = "" if message else "--edit"
    result = c.run(f'git commit {edit_flag} -m "{commit_msg}"', warn=True, pty=True)

    if result.failed:
        # Distinguish "user aborted editor" from "pre-commit hooks rejected commit".
        # Git prints "Aborting commit" when the editor is quit without saving.
        combined = (result.stdout or "") + (result.stderr or "")
        if "Aborting commit" in combined:
            print_warning("Commit aborted.")
            return
        # Pre-commit hooks fired and rejected the commit
        try:
            typer.confirm("The commit has failed due to pre-commit hooks. Commit anyway?", default=True, abort=True)
        except typer.Abort:
            print_warning("Commit aborted.")
            return
        run_command(c, "git add --all")
        run_command(c, f'git commit --no-verify {edit_flag} -m "{commit_msg}"', pty=True)

    print_success(f"Iteration #{next_number} committed!")
    c.run("git log -1")

    if push:
        run_command(c, "git push")


@task
def soft_reset(c: Context) -> None:
    """Undo all chore(ai) commits on the current branch with git reset --soft (no code is erased)."""
    git = Git(c)
    git.guard_not_default_branch()

    base_branch = git.resolve_base_ref(exit_on_failure=True)
    log_lines = _ai_log_lines(c, base_branch)

    ai_commits = [line for line in log_lines if CHORE_AI_PATTERN.search(line)]
    number = len(ai_commits)
    if not number:
        print_error("No chore(ai) commits found on this branch")
        raise SystemExit(1)

    c.run(f"git log -{number}")

    try:
        typer.confirm(
            f"\nThis will undo {number} commit(s). No code will be erased, only the commits. Are you sure?",
            abort=True,
        )
    except typer.Abort:
        print_warning("Soft reset aborted.")
        return

    # Find the hash of the oldest chore(ai) commit, then reset to its parent.
    # This is robust against interleaved merge/non-AI commits: instead of counting
    # HEAD~N (which would include unrelated commits), we pinpoint the exact commit.
    oldest_ai_hash = ai_commits[-1].split()[0]
    run_command(c, f"git reset --soft {oldest_ai_hash}~1")
    print_success(f"Soft reset done: {number} commit(s) undone, all changes are staged.")
