"""[Claude Code](https://claude.ai/code) and AI tooling maintenance tasks."""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

import typer
from invoke import Context, task

from conjuring.grimoire import print_error, print_success, print_warning, run_command, run_stdout, run_with_fzf
from conjuring.spells.git import Git

SHOULD_PREFIX = True

CHORE_AI_PATTERN = re.compile(r"chore\(ai\):\s+(\d+)")
CO_AUTHORED_BY_CLAUDE_PATTERN = re.compile(r"co-authored-by:\s+claude", re.IGNORECASE)
_LOG_RECORD_SEP = "|||END|||"
_LOG_FORMAT = f"%H|%s|%b{_LOG_RECORD_SEP}"


class _CommitInfo:
    """Parsed commit info: hash, subject, and whether it's co-authored by Claude."""

    def __init__(self, hash_: str, subject: str, body: str) -> None:
        self.hash_ = hash_
        self.subject = subject
        self.body = body
        self.is_claude = bool(CO_AUTHORED_BY_CLAUDE_PATTERN.search(body))

    @property
    def oneline(self) -> str:
        return f"{self.hash_} {self.subject}"


def _ai_log_commits(c: Context, base_branch: str) -> list[_CommitInfo]:
    """Return parsed commit info for the current branch since base_branch."""
    raw = run_stdout(c, f"git log {base_branch}..HEAD --no-merges --format='{_LOG_FORMAT}'")
    commits = []
    for raw_record in raw.split(_LOG_RECORD_SEP):
        record = raw_record.strip()
        if not record:
            continue
        # Each record is: hash|subject|body  (body may be empty)
        parts = record.split("|", 2)
        hash_ = parts[0] if parts else ""
        subject = parts[1] if len(parts) > 1 else ""
        body = parts[2] if len(parts) > 2 else ""  # noqa: PLR2004
        if hash_:
            commits.append(_CommitInfo(hash_, subject, body))
    return commits


def _ai_log_lines(c: Context, base_branch: str) -> list[str]:
    """Return commit log lines (hash + subject) for the current branch since base_branch."""
    return [commit.oneline for commit in _ai_log_commits(c, base_branch)]


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
    """Undo all chore(ai) or Claude co-authored commits on the current branch with git reset --soft."""
    git = Git(c)
    git.guard_not_default_branch()

    base_branch = git.resolve_base_ref(exit_on_failure=True)
    all_commits = _ai_log_commits(c, base_branch)

    ai_commits = [commit for commit in all_commits if CHORE_AI_PATTERN.search(commit.subject) or commit.is_claude]
    if not ai_commits:
        print_error("No chore(ai) or Claude co-authored commits found on this branch")
        raise SystemExit(1)

    # Format: "hash\tsubject" — hash is hidden via --with-nth but used in preview and recovered after selection
    lines = "\n".join(f"{commit.hash_}\t{commit.subject}" for commit in ai_commits)
    chosen = run_with_fzf(
        c,
        f"printf {shlex.quote(lines)}",
        header="Select the oldest commit to reset back to — it and all newer commits will be undone",
        preview="git show --stat --color {1}",
        options="--with-nth=2.. --delimiter='\t'",
        select_one=False,
    )
    if not chosen:
        print_warning("Soft reset aborted.")
        return

    chosen_hash = chosen.split("\t")[0]

    # ai_commits is newest-first; reset_commits = chosen commit + all newer ones above it
    chosen_idx = next(i for i, commit in enumerate(ai_commits) if commit.hash_ == chosen_hash)
    reset_commits = ai_commits[: chosen_idx + 1]
    number = len(reset_commits)

    run_command(c, f"git reset --soft {chosen_hash}~1")
    print_success(f"Soft reset done: {number} commit(s) undone, all changes are staged.")

    print("\nCommits undone:")
    for commit in reset_commits:
        full_message = commit.subject
        body = commit.body.strip()
        if body:
            full_message += "\n" + "\n".join(f"  {line}" for line in body.splitlines())
        print(f"- {full_message}")
