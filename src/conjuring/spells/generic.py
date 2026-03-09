"""Generic spells: list to-do items in files."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from shlex import quote
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

import typer
from invoke import Context, task
from more_itertools import always_iterable

from conjuring.constants import CONJURING_TOML
from conjuring.grimoire import (
    print_error,
    print_normal,
    print_success,
    print_warning,
    run_command,
    run_with_fzf,
    run_with_rg,
)

# keep-sorted start
# Split the strings to prevent this method from detecting them as tasks when running on this project
_FIX_ME = "FIX" + "ME"
_REGEX_ASSIGNEE_DESCRIPTION = re.compile(r"\s*(?P<assignee>\(.+\))?\s*:\s*(?P<description>.+)", re.IGNORECASE)
_TO_DO = "TO" + "DO"
# keep-sorted end

# Maps project-jdk-type values from misc.xml to JetBrains CLI command names
_JETBRAINS_JDK_TO_CMD = {
    "Go SDK": "goland",
    "IDEA_JDK": "idea",
    "Python SDK": "pycharm",
}


@dataclass(frozen=True)
class ToDoItem:
    """A to-do item."""

    which: str
    assignee: str
    description: str

    @property
    def sort_key(self) -> str:
        """Key to sort the instance.

        String concatenation works.
        Checking both fields separately with ``and`` conditions didn't work: sort order was not as expected
        (meaning fix-me tasks first, then to-do tasks).
        """
        return f"{self.which.casefold()}-{self.assignee.casefold()}-{self.description.casefold()}"

    def __lt__(self, other: ToDoItem) -> bool:
        return self.sort_key < other.sort_key


@dataclass
class Location:
    """Location of a to-do item in a file."""

    path: str
    line: int | str
    comment: str

    def __post_init__(self) -> None:
        self.line = int(self.line)
        self.comment = self.comment.strip()


@task(
    help={
        "cz": "Run commitizen (cz check) to validate the description of the to-do item as a commit message",
        "valid": "When using cz check, print valid to-do items",
        "invalid": "When using cz check, print invalid to-do items",
        "short": "Short format: only the description, without the lines of code where to-do items were found",
        "priority": "Specify an assignee and show only higher priority tasks for them"
        f" ({_FIX_ME} or {_TO_DO}(<assignee>)",
        "markdown": "Print the output in Markdown format",
        "dir": "Partial directory names to search for items. Use multiple times or a comma-separated list",
    },
    iterable=["dir"],
)
def todo(  # noqa: C901,PLR0913,PLR0912
    c: Context,
    cz: bool = False,
    valid: bool = True,
    invalid: bool = True,
    short: bool = False,
    priority: str = "",
    markdown: bool = False,
    dir_: str = "",
) -> None:
    """List to-dos and fix-mes in code. Optionally check if the description follows Conventional Commits (cz check)."""
    dir_names = []
    if dir_:
        for one_dir in always_iterable(dir_):
            if "," in one_dir:
                dir_names.extend(one_dir.split(","))
            else:
                dir_names.append(one_dir)
    all_todos: dict[ToDoItem, list[Location]] = _parse_all_todos(c, priority, dir_names)

    if markdown:
        _print_todos_as_markdown(all_todos, short)
        return

    for item, locations in sorted(all_todos.items()):  # type: ToDoItem, list[Location]
        func = print_success
        if cz:
            result = run_command(c, "cz check -m", quote(item.description), hide=True, warn=True)
            if result.ok:
                if not valid:
                    continue
            else:
                if not invalid:
                    continue
                func = print_error

        assignee_str = f"({item.assignee.upper()})" if item.assignee else ""
        func(f"{item.which}{assignee_str}: {item.description}")

        if short:
            continue
        for loc in locations:  # type: Location
            typer.echo(f"   {loc.path}:{loc.line} {loc.comment}")


def _print_todos_as_markdown(all_todos: dict[ToDoItem, list[Location]], short: bool) -> None:
    bullets = []
    for item, locations in all_todos.items():  # type: ToDoItem, list[Location]
        bullet = f"- {item.description}"
        if not short:
            all_paths = ", ".join(sorted(f"`{loc.path}:{loc.line}`" for loc in locations))
            bullet += f" ({all_paths})"
        bullets.append(bullet)
    for bullet in sorted(bullets):
        print_normal(bullet)


def _parse_all_todos(c: Context, priority: str, dir_names: list[str]) -> dict[ToDoItem, list[Location]]:
    all_todos: dict[ToDoItem, list[Location]] = defaultdict(list)
    priority = priority.casefold()
    for which in (_FIX_ME, _TO_DO):
        for rg_match in run_with_rg(c, which):
            _before, after = rg_match.text.split(which, maxsplit=1)  # type: str,str

            match = _REGEX_ASSIGNEE_DESCRIPTION.match(after)
            if match:
                assignee = (match.group("assignee") or "").strip("()").casefold()
                if priority and not (which == _FIX_ME or assignee == priority):
                    continue
                description = (match.group("description") or "").strip()
            else:
                assignee = ""
                description = after.strip()
            key = ToDoItem(which, assignee, description)

            location = Location(
                path=rg_match.path,
                line=rg_match.line,
                comment="",
            )
            if dir_names and not any(dir_name in location.path for dir_name in dir_names):
                continue
            all_todos[key].append(location)
    return all_todos


def _resolve_idea_path(raw: str, project_dir: Path) -> Path | None:
    """Resolve a modules.xml filepath, expanding $PROJECT_DIR$ and $USER_HOME$."""
    expanded = raw.replace("$USER_HOME$", str(Path.home())).replace("$PROJECT_DIR$", str(project_dir))
    p = Path(expanded).resolve()
    return p if p.exists() else None


def _detect_jetbrains_cmd(idea_dir: Path) -> str:
    """Detect the JetBrains IDE command from misc.xml's project-jdk-type."""
    misc = idea_dir / "misc.xml"
    if misc.exists():
        root = ET.parse(misc).getroot()  # noqa: S314
        for comp in root.iter("component"):
            if comp.get("name") == "ProjectRootManager":
                jdk_type = comp.get("project-jdk-type", "")
                return _JETBRAINS_JDK_TO_CMD.get(jdk_type, "idea")
    return "idea"


def _parents_from_config(cwd: Path) -> list[Path]:
    """Read parent project paths from the [jetbrains] section of conjuring.toml."""
    toml_file = cwd / CONJURING_TOML
    if not toml_file.exists():
        return []
    if TYPE_CHECKING:
        import tomllib
    else:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
    data = tomllib.loads(toml_file.read_text())
    parents = []
    for raw in data.get("jetbrains", {}).get("parents", []):
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            parents.append(p)
        else:
            print_warning(f"conjuring.toml [jetbrains] parents: path not found, skipping: {raw}")
    return parents


def _hosts_from_xml(cwd: Path, modules_xml: Path) -> list[Path]:
    """Scan modules listed in modules.xml for ones whose own modules.xml back-references cwd."""
    root = ET.parse(modules_xml).getroot()  # noqa: S314
    cwd_name = cwd.name
    found = []

    for module_el in root.iter("module"):
        filepath = module_el.get("filepath", "")
        resolved = _resolve_idea_path(filepath, cwd)
        if resolved is None:
            print_warning(f"modules.xml: path not found, skipping: {filepath}")
            continue
        candidate_dir = resolved.parent.parent  # .idea/../ = project root
        if candidate_dir == cwd:
            continue  # skip self

        candidate_modules_xml = candidate_dir / ".idea" / "modules.xml"
        if not candidate_modules_xml.exists():
            continue

        candidate_root = ET.parse(candidate_modules_xml).getroot()  # noqa: S314
        for el in candidate_root.iter("module"):
            if cwd_name in el.get("filepath", ""):
                found.append(candidate_dir)
                break

    return found


@task
def jetbrains(c: Context) -> None:
    """Open the current project (or its parent project) in the correct JetBrains IDE.

    Parent project resolution order:
    1. conjuring.toml [jetbrains] parents list at the project root.
    2. Reverse-reference scan of modules listed in .idea/modules.xml.
    3. Current directory (fallback).

    When multiple parents are found, fzf is used to pick one interactively.
    Each fzf entry is formatted as "<cmd> <path>" so you can see both the IDE and the target.
    """
    cwd = Path.cwd().resolve()
    idea_dir = cwd / ".idea"

    if not idea_dir.is_dir():
        print_error(f"No .idea directory found in {cwd}")
        raise SystemExit(1)

    # 1. conjuring.toml [jetbrains] parents takes priority
    parents = _parents_from_config(cwd)

    # 2. XML reverse-reference scan (only when no config)
    if not parents:
        modules_xml = idea_dir / "modules.xml"
        if modules_xml.exists():
            parents = _hosts_from_xml(cwd, modules_xml)

    # Build "<cmd> <path>" entries for each parent
    if parents:
        entries = [f"{_detect_jetbrains_cmd(p / '.idea')} {p}" for p in parents]
    else:
        entries = [f"{_detect_jetbrains_cmd(idea_dir)} {cwd}"]

    if len(entries) == 1:
        choice = entries[0]
    else:
        choice = run_with_fzf(c, *[f"echo {quote(e)}" for e in entries], header="Select parent project", pty=True)

    cmd, _, path = choice.partition(" ")
    print_normal(f"Opening: {choice}")
    run_command(c, cmd, path)
