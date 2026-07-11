"""[Claude Code](https://claude.ai/code) and AI tooling maintenance tasks."""

from __future__ import annotations

import fnmatch
import re
import shlex
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.table import Table

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
_GSD_HIDDEN_STATUSES = {"complete"}
_HIDDEN_STATUSES = {"complete", "canceled", "superseded"}
_LOG_RECORD_SEP = "|||END|||"
_MISSING = "missing"
_PHASE_STATUS_SYMBOLS = {"complete": "✓", "pending": "…", "in_progress": "▶"}
# keep-sorted end

# These need to be out of the keep sorted block
_STATUS_COLORS = {
    "approved": "green",
    "canceled": "red",
    "complete": "green",
    "ignored": "yellow",
    "missing": "red",
    "partial": "yellow",
    "superseded": "magenta",
}
_GSD_PHASE_STATUS_COLORS = {
    "complete": "green",
    "in_progress": "yellow",
    "partial": "yellow",
    "planned": "cyan",
    "pending": "dim",
}
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


@task
def iteration(c: Context, message: str = "", push: bool = False) -> None:
    """Commit all changes as a numbered AI iteration (e.g. chore(ai): 3. <message>)."""
    git = Git(c)
    git.warn_if_default_branch()

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


def _main_repo_root(repo_root: Path) -> Path:
    """Return the main repo root, resolving worktree .git file pointers if needed."""
    git_dir = repo_root / ".git"
    if git_dir.is_file():
        # .git file content: "gitdir: /path/to/main/.git/worktrees/<name>"
        gitdir_path = Path(git_dir.read_text().strip().removeprefix("gitdir: "))
        # Walk up from .git/worktrees/<name> to the main repo root
        main_root = (gitdir_path / "../../..").resolve()
        if main_root != repo_root:
            return main_root
    return repo_root


def _load_plans_ignore(main_root: Path) -> list[str]:
    """Load plans_ignore from [_.conjuring.ai] in mise.local.toml at the main repo root."""
    return _mise_plans_ignore(main_root)


def _list_worktrees(main_root: Path) -> list[Path]:
    """Return all worktree paths for this repo, main worktree first."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],  # noqa: S607
            capture_output=True,
            text=True,
            cwd=main_root,
            check=False,
        )
    except OSError:
        return [main_root]
    paths = [
        Path(line.removeprefix("worktree ")) for line in result.stdout.splitlines() if line.startswith("worktree ")
    ]
    return paths or [main_root]


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


def _worktree_label(wt: Path, main_root: Path) -> str:
    """Return a display label for a worktree path relative to main_root, or absolute if outside."""
    try:
        return "./" + str(wt.relative_to(main_root))
    except ValueError:
        return str(wt)


def _add_rows_to_table(table: Table, rows: list[tuple[str, list[str]]], columns: list[str], status_idx: int) -> None:
    """Append styled plan rows to a Rich Table."""
    for file_path, row in rows:
        status_cell = row[status_idx] if status_idx >= 0 else ""
        base_status = status_cell.split(" (")[0] if " (" in status_cell else status_cell
        color = _STATUS_COLORS.get(base_status, "")
        styled_row = [
            f"[{color}]{cell}[/{color}]" if color and col in {"status", "last_updated"} else cell
            for col, cell in zip(columns, row)
        ]
        table.add_row(file_path, *styled_row)


def _render_plans_table(
    worktrees: list[Path],
    worktree_rows: dict[Path, list[tuple[str, list[str]]]],
    main_root: Path,
    columns: list[str],
    all_: bool,
) -> None:
    """Build and print the Rich plans table, grouped by worktree."""
    from rich.console import Console
    from rich.table import Table

    title = ("All" if all_ else "Pending") + " AI Plans & Specs"
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan", no_wrap=False)
    for col in columns:
        table.add_column(col.replace("_", " ").title())

    status_idx = columns.index("status") if "status" in columns else -1
    _add_rows_to_table(table, worktree_rows[main_root], columns, status_idx)

    for wt in worktrees[1:]:
        rows = worktree_rows[wt]
        if not rows:
            continue
        table.add_row(f"> {_worktree_label(wt, main_root)}", *[""] * len(columns), style="bold cyan")
        _add_rows_to_table(table, rows, columns, status_idx)

    Console().print(table)


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

    main_root = _main_repo_root(_repo_root)
    worktrees = _list_worktrees(main_root)
    ignore_patterns = _load_plans_ignore(main_root)
    plan_dirs = dirs or list(_DEFAULT_PLAN_DIRS)

    # Collect md files and frontmatter across all worktrees
    worktree_md: dict[Path, list[Path]] = {}
    all_fm: dict[Path, dict[str, str]] = {}
    for wt in worktrees:
        search_dirs = [wt / d for d in plan_dirs]
        md_files = sorted(path for sd in search_dirs if sd.is_dir() for path in sd.rglob("*.md"))
        worktree_md[wt] = md_files
        for path in md_files:
            all_fm[path] = _parse_all_frontmatter(path)

    if not any(worktree_md.values()):
        print_warning("No Markdown files found in any worktree")
        return

    columns = _plan_columns(all_fm, dynamic)

    # Build rows per worktree
    worktree_rows: dict[Path, list[tuple[str, list[str]]]] = {}
    for wt, md_files in worktree_md.items():
        worktree_rows[wt] = _plan_rows(md_files, all_fm, wt, columns, ignore_patterns, all_)

    total_rows = sum(len(r) for r in worktree_rows.values())
    if total_rows == 0:
        print_success("All superpowers plans are completed")
    else:
        _render_plans_table(worktrees, worktree_rows, main_root, columns, all_)

    # Show GSD phase table if this repo has a .planning dir
    if (main_root / ".planning").is_dir():
        _show_gsd_table(main_root, all_)


_GSD_ROADMAP_PHASE = re.compile(
    r"(?:"
    r"^#{1,3} Phase\s+(\S+)\s+[-:]\s+(.+)"  # ## Phase N - Name  or  ### Phase N: Name
    r"|"
    r"^\s*-\s+\[( |x|~)\]\s+\*\*Phase\s+(\S+):\s+(.+?)\*\*"  # - [ ] / - [x] / - [~] **Phase N: Name**
    r")",
    re.MULTILINE,
)


def _gsd_roadmap_phases(cwd: Path) -> list[dict]:
    """Parse ROADMAP.md for all Phase entries, returning [{number, name, checked}]."""
    roadmap = cwd / ".planning" / "ROADMAP.md"
    if not roadmap.exists():
        return []
    text = roadmap.read_text()
    seen: set[str] = set()
    phases = []
    for m in _GSD_ROADMAP_PHASE.finditer(text):
        # Heading style: groups 1+2, no checkbox. Checklist style: groups 3(check)+4+5.
        if m.group(1) is not None:
            num, name, checked = m.group(1).strip(), m.group(2).strip(), None
        else:
            checked, num, name = m.group(3), m.group(4).strip(), m.group(5).strip()
        if not num or num in seen:
            continue
        seen.add(num)
        # Skip milestone-marker headings like "Phase 1 - Complete (shipped v0.2.x)"
        if re.match(r"complete\b", name, re.IGNORECASE):
            continue
        # Strip trailing tags like [NEXT], (conditional), (immediate)
        name = re.sub(r"\s*[\[(][^\])]+[\])]$", "", name).strip()
        phases.append({"number": num, "name": name, "checked": checked})
    return phases


def _archived_phase_plan_counts(cwd: Path, num: str) -> tuple[int, int]:
    """Return (plan_count, summary_count) for a phase by scanning archived milestone dirs.

    init.progress only reports counts for the current milestone's phase directories;
    phases from prior completed milestones move under .planning/archive/<milestone>/<num>-*/.
    """
    archive_root = cwd / ".planning" / "archive"
    if not archive_root.is_dir():
        return 0, 0
    padded = num.zfill(2)
    for phase_dir in archive_root.glob(f"*/{padded}-*"):
        if not phase_dir.is_dir():
            continue
        plan_count = len(list(phase_dir.glob("*PLAN.md")))
        summary_count = len(list(phase_dir.glob("*SUMMARY.md")))
        return plan_count, summary_count
    return 0, 0


def _gsd_query(cwd: Path, query: str) -> dict:
    """Run a gsd-tools query and return parsed JSON, or {} on failure."""
    import json
    import subprocess

    try:
        result = subprocess.run(  # noqa: S603
            ["gsd-tools", "query", query, "--raw", "--cwd", str(cwd)],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _gsd_phase_rows(phases: list[dict], all_: bool) -> list[tuple[str, str, str, str]]:
    """Build GSD phase rows as (phase, name, status, plans) tuples."""
    rows = []
    for phase in phases:
        status = phase.get("status", "")
        if not all_ and status in _GSD_HIDDEN_STATUSES:
            continue
        plan_count = phase.get("plan_count", 0)
        summary_count = phase.get("summary_count", 0)
        plans_cell = f"{summary_count}/{plan_count}"
        rows.append(
            (
                phase.get("number", ""),
                phase.get("name", ""),
                status,
                plans_cell,
            )
        )
    return rows


_QUICK_SLUG = re.compile(r"^\d{6,8}-[a-z0-9]{3}-")


_QUICK_FRONTMATTER_FIELD = re.compile(r"^(status|last_updated):\s*(.+?)\s*$", re.MULTILINE)


def _quick_task_status(quick_dir: Path) -> tuple[str, str]:
    """Return (status, last_updated) for a quick task, read from its SUMMARY*.md frontmatter."""
    for summary in sorted(quick_dir.glob("*SUMMARY*.md")):
        text = summary.read_text(errors="ignore")
        fields = dict(_QUICK_FRONTMATTER_FIELD.findall(text.split("\n---", 1)[0]))
        if fields.get("status"):
            return fields["status"], fields.get("last_updated", "")
    return _MISSING, ""


def _quick_task_rows(cwd: Path, all_: bool) -> list[tuple[str, str, str, str]]:
    """Build quick-task rows as (phase, name, status, plans) tuples."""
    quick_root = cwd / ".planning" / "quick"
    if not quick_root.is_dir():
        return []

    rows = []
    for quick_dir in sorted(quick_root.iterdir()):
        if not quick_dir.is_dir():
            continue
        status, _last_updated = _quick_task_status(quick_dir)
        if not all_ and status in _GSD_HIDDEN_STATUSES:
            continue
        name = _QUICK_SLUG.sub("", quick_dir.name)
        rows.append(("quick", name, status, ""))
    return rows


def _render_gsd_table(rows: list[tuple[str, str, str, str]], milestone: str) -> None:
    """Print a Rich table of GSD phases and quick tasks."""
    from rich.console import Console
    from rich.table import Table

    title = f"GSD Phases — {milestone}" if milestone else "GSD Phases"
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Phase", no_wrap=True)
    table.add_column("Name", style="cyan")
    table.add_column("Status")
    table.add_column("Plans", justify="right")

    for phase_num, name, status, plans_cell in rows:
        color = _GSD_PHASE_STATUS_COLORS.get(status, "") or _STATUS_COLORS.get(status, "")
        status_cell = f"[{color}]{status}[/{color}]" if color else status
        table.add_row(phase_num, name, status_cell, plans_cell)

    Console().print(table)


def _show_gsd_table(cwd: Path, all_: bool) -> None:
    """Detect and render a combined GSD phase + quick task table for the given project root."""
    import shutil

    if not shutil.which("gsd-tools"):
        print_warning("gsd-tools not on PATH - install: npx -y @opengsd/gsd-core@latest")
        return

    data = _gsd_query(cwd, "init.progress")
    roadmap_phases = _gsd_roadmap_phases(cwd)

    if not data and not roadmap_phases:
        return

    # Build a map of known phases from init.progress (have artifact dirs).
    # Normalize keys: strip leading zeros so "00" and "0" both match.
    known: dict[str, dict] = {p["number"].lstrip("0") or "0": p for p in data.get("phases", [])}

    # Merge: roadmap order, filling in artifact data where available
    phases: list[dict] = []
    for rp in roadmap_phases:
        num = rp["number"]
        if num in known:
            phases.append(known[num])
        else:
            checked = rp.get("checked")
            status = "complete" if checked == "x" else "in_progress" if checked == "~" else "planned"
            plan_count, summary_count = _archived_phase_plan_counts(cwd, num)
            phases.append(
                {
                    "number": num,
                    "name": rp["name"],
                    "status": status,
                    "plan_count": plan_count,
                    "summary_count": summary_count,
                }
            )

    # Fall back to init.progress phases if ROADMAP.md has no headings
    if not phases:
        phases = data.get("phases", [])

    rows = _gsd_phase_rows(phases, all_) if phases else []
    rows += _quick_task_rows(cwd, all_)

    if not rows:
        print_success("All GSD phases and quick tasks completed")
        return

    milestone = data.get("milestone_version", "")
    _render_gsd_table(rows, milestone)


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
