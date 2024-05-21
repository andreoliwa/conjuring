"""Generic spells: list to-do items in files."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from shlex import quote

import typer
from invoke import Context, task
from more_itertools import always_iterable

from conjuring.grimoire import print_error, print_normal, print_success, run_command, run_with_rg

# keep-sorted start
# Split the strings to prevent this method from detecting them as tasks when running on this project
FIX_ME = "FIX" + "ME"
REGEX_ASSIGNEE_DESCRIPTION = re.compile(r"\s*(?P<assignee>\(.+\))?\s*:\s*(?P<description>.+)", re.IGNORECASE)
TO_DO = "TO" + "DO"
# keep-sorted end


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
        f" ({FIX_ME} or {TO_DO}(<assignee>)",
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
    for which in (FIX_ME, TO_DO):
        for rg_match in run_with_rg(c, which):
            before, after = rg_match.text.split(which, maxsplit=1)  # type: str,str

            match = REGEX_ASSIGNEE_DESCRIPTION.match(after)
            if match:
                assignee = (match.group("assignee") or "").strip("()").casefold()
                if priority and not (which == FIX_ME or assignee == priority):
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
