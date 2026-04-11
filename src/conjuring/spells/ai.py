"""[Claude Code](https://claude.ai/code) and AI tooling maintenance tasks."""

from __future__ import annotations

import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

from invoke import Context, task

from conjuring.grimoire import (
    ask_yes_no,
    print_error,
    print_success,
    print_warning,
    run_command,
    run_stdout,
    run_with_fzf,
)
from conjuring.spells.git import Git, log_since

# keep-sorted start
AI_COMMITS_FILE_PREFIX = "ai-commits-"
CHORE_AI_PATTERN = re.compile(r"chore\(ai\):\s+(\d+)")
SHOULD_PREFIX = True
_DEFAULT_PLAN_DIRS = ("docs/superpowers", "docs/plans")
_FRONTMATTER_BLOCK = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_LOG_RECORD_SEP = "|||END|||"
_MISSING = "[bold red]MISSING[/bold red]"
# keep-sorted end

_LOG_FORMAT = f"%H|%s|%b{_LOG_RECORD_SEP}"


class _CommitInfo:
    """Parsed commit info: hash, subject, and body."""

    def __init__(self, hash_: str, subject: str, body: str) -> None:
        self.hash_ = hash_
        self.subject = subject
        self.body = body

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
    commit_msg = f"chore(ai): {next_number}. {message or 'human review'}"

    # Stage all changes, excluding ai-commits-* report files
    git_add = f"git add --all -- ':(exclude){AI_COMMITS_FILE_PREFIX}*'"
    run_command(c, git_add)

    result = c.run(f'git commit -m "{commit_msg}"', warn=True, pty=True)

    if result.failed:
        # Pre-commit hooks fired and rejected the commit
        if not ask_yes_no("The commit has failed due to pre-commit hooks. Commit anyway?"):
            print_warning("Commit aborted.")
            return
        run_command(c, git_add)
        run_command(c, f'git commit --no-verify -m "{commit_msg}"', pty=True)

    print_success(f"Iteration #{next_number} committed!")
    log_since(c, base_branch)

    if push:
        run_command(c, "git push")


@task
def soft_reset(c: Context) -> None:
    """Pick a commit to reset back to (soft reset) — shows all commits since the base branch."""
    git = Git(c)

    base_branch = git.resolve_base_ref(exit_on_failure=True)
    all_commits = _ai_log_commits(c, base_branch)

    if not all_commits:
        print_error("No commits found on this branch since the base branch")
        raise SystemExit(1)

    # Format: "hash\t{number}. {subject}" — hash is hidden via --with-nth but recovered after selection
    lines = "\n".join(f"{commit.hash_}\t{i + 1}. {commit.subject}" for i, commit in enumerate(all_commits))
    chosen = run_with_fzf(
        c,
        f"printf {shlex.quote(lines)}",
        header="Select the oldest commit to reset back to — it and all newer commits will be undone",
        preview="git show --stat --color {1}",
        options="--with-nth=2.. --delimiter='\t' --preview-window=down,80%,wrap",
        select_one=False,
        hide=True,
    )
    if not chosen:
        print_warning("Soft reset aborted.")
        return

    chosen_hash = chosen.split("\t")[0]

    # all_commits is newest-first; reset_commits = chosen commit + all newer ones above it
    chosen_idx = next(i for i, commit in enumerate(all_commits) if commit.hash_ == chosen_hash)
    reset_commits = all_commits[: chosen_idx + 1]
    number = len(reset_commits)

    run_command(c, f"git reset --soft {chosen_hash}~1")
    print_success(f"Soft reset done: {number} commit(s) undone, all changes are staged.")

    current_dt = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    lines_md = [f"# Undone commits {current_dt}\n"]
    for commit in reset_commits:
        body = commit.body.strip()
        lines_md.append(f"- {commit.subject}")
        if body:
            lines_md.append(body + "\n")

    filename = f"{AI_COMMITS_FILE_PREFIX}{current_dt}.md"
    Path(filename).write_text("\n".join(lines_md))
    print_success(f"Undone commits saved to {filename}")
    c.run(f"cat {filename}")


def _plan_columns(all_fm: dict[Path, dict[str, str]], dynamic: bool) -> list[str]:
    """Return column names for the plans table."""
    if not dynamic:
        return ["status", "last_updated"]
    seen: dict[str, None] = {}
    for fm in all_fm.values():
        seen.update(dict.fromkeys(fm))
    return list(seen)


def _parse_all_frontmatter(path: Path) -> dict[str, str]:
    """Return all key-value pairs from a Markdown file's YAML frontmatter."""
    text = path.read_text()
    fm_match = _FRONTMATTER_BLOCK.match(text)
    if not fm_match:
        return {}
    result = {}
    for line in fm_match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


@task(
    help={
        "dirs": f"Directories to scan for plan/spec Markdown files (relative to repo root). "
        f"Default: {', '.join(_DEFAULT_PLAN_DIRS)}",
        "dynamic": "Discover columns dynamically from all frontmatter keys found "
        "(default: fixed status + last_updated)",
        "all_": "Show all plans including completed ones (default: hide status=complete)",
    },
    iterable=["dirs"],
)
def plans(c: Context, dirs: list[str], dynamic: bool = False, all_: bool = False) -> None:
    """Display plans and specs with their frontmatter status and last_updated date."""
    _repo_root = Git(c).repo_root(quiet=True)
    if not _repo_root:
        return
    repo_root: Path = _repo_root

    search_dirs = [repo_root / d for d in (dirs or _DEFAULT_PLAN_DIRS)]

    md_files = sorted(path for search_dir in search_dirs if search_dir.is_dir() for path in search_dir.rglob("*.md"))

    if not md_files:
        print_warning("No Markdown files found in: " + ", ".join(str(d) for d in search_dirs))
        return

    # Parse frontmatter for all files upfront
    all_fm = {path: _parse_all_frontmatter(path) for path in md_files}
    columns = _plan_columns(all_fm, dynamic)

    rows: list[tuple[str, list[str]]] = []
    for path in md_files:
        fm = all_fm[path]
        if not all_ and fm.get("status") == "complete":
            continue
        rel = path.relative_to(repo_root)
        rows.append((str(rel), [fm.get(col) or _MISSING for col in columns]))

    if not rows:
        if not md_files:
            print_warning("This repo has no AI plans")
        else:
            print_success("All AI plans are completed")
        return

    from rich.console import Console
    from rich.table import Table

    title = ("All" if all_ else "Incomplete/Missing") + " AI Plans & Specs"
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan", no_wrap=False)
    for col in columns:
        table.add_column(col.replace("_", " ").title())

    for file_path, row in rows:
        table.add_row(file_path, *row)

    Console().print(table)
