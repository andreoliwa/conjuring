"""[Claude Code](https://claude.ai/code) and AI tooling maintenance tasks."""

from __future__ import annotations

import fnmatch
import re
import shlex
import sys
from datetime import date, datetime, timezone
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
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
SHOULD_PREFIX = True
_DEFAULT_PLAN_DIRS = ("docs/superpowers", "docs/plans")
_FRONTMATTER_BLOCK = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_HIDDEN_STATUSES = {"complete", "canceled", "superseded"}
_LOG_RECORD_SEP = "|||END|||"
_MISSING = "missing"
_PHASE_STATUS_SYMBOLS = {"complete": "✓", "pending": "…", "in_progress": "▶"}
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


def _format_phases(phases: list) -> str:
    """Render a phases list as a compact summary string, e.g. '✓ Phase 1 | … Phase 3'."""
    parts = []
    for phase in phases:
        name = phase.get("name", "?")
        symbol = _PHASE_STATUS_SYMBOLS.get(phase.get("status", ""), "?")
        parts.append(f"{symbol} {name}")
    return "\n".join(parts)


def _parse_all_frontmatter(path: Path) -> dict[str, str]:
    """Return top-level frontmatter as strings; phases lists are rendered as a compact summary."""
    from ruamel.yaml import YAML

    text = path.read_text()
    fm_match = _FRONTMATTER_BLOCK.match(text)
    if not fm_match:
        return {}
    parsed = YAML().load(fm_match.group(1)) or {}
    result = {k: str(v) for k, v in parsed.items() if isinstance(v, str | int | float | bool | date)}
    if "phases" in parsed and isinstance(parsed["phases"], list):
        result["phases"] = _format_phases(parsed["phases"])
    return result


def _mise_plans_ignore(directory: Path) -> list[str]:
    """Try loading plans_ignore from [_.conjuring.ai] in mise configs under directory."""
    import tomllib

    for name in ("mise.local.toml", "mise.toml"):
        path = directory / name
        if not path.exists():
            continue
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        ignore = data.get("_", {}).get("conjuring", {}).get("ai", {}).get("plans_ignore", [])
        if ignore:
            return ignore if isinstance(ignore, list) else [ignore]
    return []


def _load_plans_ignore(repo_root: Path) -> list[str]:
    """Load plans_ignore patterns, checking repo_root and (for worktrees) the main repo root."""
    ignore = _mise_plans_ignore(repo_root)
    if ignore:
        return ignore
    # In a git worktree, .git is a file pointing to the main repo; check the main root too
    git_dir = repo_root / ".git"
    if git_dir.is_file():
        # .git file content: "gitdir: /path/to/main/.git/worktrees/<name>"
        gitdir_path = Path(git_dir.read_text().strip().removeprefix("gitdir: "))
        # Walk up from .git/worktrees/<name> to the main repo root
        main_root = (gitdir_path / "../../..").resolve()
        if main_root != repo_root:
            return _mise_plans_ignore(main_root)
    return []


def _is_ignored(rel_path: str, patterns: list[str]) -> bool:
    """Check if a relative path matches any of the ignore patterns."""
    return any(fnmatch.fnmatch(rel_path, pat) for pat in patterns)


def _plan_rows(  # noqa: PLR0913
    md_files: list[Path],
    all_fm: dict[Path, dict[str, str]],
    repo_root: Path,
    columns: list[str],
    ignore_patterns: list[str],
    all_: bool,
) -> list[tuple[str, list[str]]]:
    """Build table rows for plans, applying status and ignore filters."""
    rows: list[tuple[str, list[str]]] = []
    for path in md_files:
        fm = all_fm[path]
        rel = str(path.relative_to(repo_root))
        ignored = _is_ignored(rel, ignore_patterns)
        if not all_ and (fm.get("status") in _HIDDEN_STATUSES or ignored):
            continue
        if ignored:
            original = fm.get("status") or "missing"
            fm = {**fm, "status": f"{original} (ignored)"}
            all_fm[path] = fm
        rows.append((rel, [fm.get(col) or (_MISSING if col in {"status", "last_updated"} else "") for col in columns]))
    return rows


@task(
    help={
        "dirs": f"Directories to scan for plan/spec Markdown files (relative to repo root). "
        f"Default: {', '.join(_DEFAULT_PLAN_DIRS)}",
        "dynamic": "Discover columns dynamically from all frontmatter keys found "
        "(default: fixed status + last_updated)",
        "all_": "Show all plans including completed/canceled/superseded/ignored ones",
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
    ignore_patterns = _load_plans_ignore(repo_root)

    rows = _plan_rows(md_files, all_fm, repo_root, columns, ignore_patterns, all_)

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

    _status_colors = {
        "approved": "green",
        "complete": "green",
        "missing": "red",
        "partial": "yellow",
        "canceled": "red",
        "ignored": "yellow",
        "superseded": "magenta",
    }
    status_idx = columns.index("status") if "status" in columns else -1
    for file_path, row in rows:
        status_cell = row[status_idx] if status_idx >= 0 else ""
        # For compound statuses like "complete (ignored)", color by the base status
        base_status = status_cell.split(" (")[0] if " (" in status_cell else status_cell
        color = _status_colors.get(base_status, "")
        styled_row = [
            f"[{color}]{cell}[/{color}]" if color and col in {"status", "last_updated"} else cell
            for col, cell in zip(columns, row)
        ]
        table.add_row(file_path, *styled_row)

    Console().print(table)


def _decode_project_dir(encoded: str) -> str:
    """Decode a Claude project directory name back to a readable path.

    The encoding joins path segments with '-', so '-Users-aa-dev-me-my-den' could be
    /Users/aa/dev/me/my-den or /Users/aa/dev/me/my/den.  We walk the filesystem to
    greedily resolve the longest existing directory at each level.
    """
    if not encoded.startswith("-"):
        return encoded
    # Strip worktree suffix (e.g. '--claude-worktrees-fancy-name')
    base = encoded.split("--", maxsplit=1)[0] if "--" in encoded else encoded
    parts = base[1:].split("-")  # drop leading '-', split remaining
    # Greedy reconstruction: try longest segment combos that exist on disk
    current = Path("/")
    i = 0
    while i < len(parts):
        # Try joining progressively more parts as a single directory name
        best = None
        for j in range(len(parts), i, -1):
            candidate = "-".join(parts[i:j])
            if (current / candidate).exists():
                best = (candidate, j)
                break
        if best:
            current = current / best[0]
            i = best[1]
        else:
            # No match on disk; just use the single part
            current = current / parts[i]
            i += 1
    return str(current)


def _extract_text(content: str | list) -> str:
    """Extract searchable text from a message content field.

    Handles: plain strings (user messages), text blocks, and tool_result blocks (which
    contain file contents, command output, etc. that are often the most searchable parts).
    """
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif block.get("type") == "tool_result":
            # tool_result content can be a string or a list of content blocks
            inner = block.get("content", "")
            if isinstance(inner, str):
                parts.append(inner)
            elif isinstance(inner, list):
                parts.extend(
                    sub.get("text", "") for sub in inner if isinstance(sub, dict) and sub.get("type") == "text"
                )
    return "\n".join(parts)


def _search_conversations(query: str, project: str = "") -> list[dict]:
    """Search JSONL conversation files for a query string, returning match info.

    Returns a list of dicts with keys: project, session_id, timestamp, role, snippet.
    """
    import json

    search_dir = CLAUDE_PROJECTS_DIR
    if project:
        # Find matching project dir(s)
        matches = sorted(search_dir.glob(f"*{project}*"))
        if not matches:
            print_error(f"No project directory matching '{project}'")
            return []
        search_dir = matches[0]

    results = []
    # Only search JSONL files directly under project dirs (skip subagent subdirs)
    if search_dir == CLAUDE_PROJECTS_DIR:
        jsonl_files = sorted(f for d in search_dir.iterdir() if d.is_dir() for f in d.glob("*.jsonl"))
    else:
        jsonl_files = sorted(search_dir.glob("*.jsonl"))
    for jsonl_path in jsonl_files:
        project_dir = jsonl_path.parent.name
        session_id = jsonl_path.stem
        with jsonl_path.open() as fh:
            for line in fh:
                if query.lower() not in line.lower():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") not in ("user", "assistant"):
                    continue
                msg = record.get("message", {})
                text = _extract_text(msg.get("content", ""))
                if query.lower() not in text.lower():
                    continue
                # Build a short snippet around the match
                lower_text = text.lower()
                idx = lower_text.find(query.lower())
                start = max(0, idx - 60)
                end = min(len(text), idx + len(query) + 60)
                prefix = "..." if start > 0 else ""
                suffix = "..." if end < len(text) else ""
                snippet = prefix + text[start:end].replace("\n", " ") + suffix
                results.append(
                    {
                        "project": project_dir,
                        "session_id": session_id,
                        "timestamp": record.get("timestamp", ""),
                        "role": record.get("type", ""),
                        "snippet": snippet,
                    }
                )
    return results


@task(
    help={
        "query": "Text to search for in Claude Code conversations",
        "project": "Filter to a specific project (partial match on directory name)",
        "projects_only": "Only list matching project directories, not individual matches",
    },
)
def convos(c: Context, query: str, project: str = "", projects_only: bool = False) -> None:
    """Search across Claude Code conversations for a topic."""
    if not CLAUDE_PROJECTS_DIR.is_dir():
        print_error(f"Claude projects directory not found: {CLAUDE_PROJECTS_DIR}")
        raise SystemExit(1)

    if projects_only:
        # Fast path: use rg to find which project dirs contain the query
        rg_output = run_stdout(c, f"rg -li {shlex.quote(query)} {CLAUDE_PROJECTS_DIR}", quiet=True)
        if not rg_output:
            print_warning(f"No conversations found matching '{query}'")
            return
        # Only keep direct children of CLAUDE_PROJECTS_DIR (skip subagent subdirs)
        top_level_dirs = {d.name for d in CLAUDE_PROJECTS_DIR.iterdir() if d.is_dir()}
        project_dirs = sorted(
            {Path(line).parent.name for line in rg_output.splitlines() if Path(line).parent.name in top_level_dirs}
        )
        from rich.console import Console
        from rich.table import Table

        table = Table(title=f"Projects discussing '{query}'", show_header=True, header_style="bold magenta")
        table.add_column("Project Directory", style="cyan")
        table.add_column("Path", style="dim")
        for proj_dir in project_dirs:
            table.add_row(proj_dir, _decode_project_dir(proj_dir))
        Console().print(table)
        return

    results = _search_conversations(query, project)
    if not results:
        print_warning(f"No conversations found matching '{query}'")
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(title=f"Conversations matching '{query}'", show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan", no_wrap=False, max_width=30)
    table.add_column("Timestamp", style="dim", no_wrap=True)
    table.add_column("Role", style="green")
    table.add_column("Snippet", no_wrap=False)

    for r in results:
        ts = r["timestamp"][:19].replace("T", " ") if r["timestamp"] else ""
        table.add_row(_decode_project_dir(r["project"]), ts, r["role"], r["snippet"])

    Console().print(table)
