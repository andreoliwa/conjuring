"""Generic spells that don't have a prefix and don't fit other modules."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from shlex import quote

from invoke import task

from conjuring.grimoire import print_error, print_success, run_command, run_lines


@dataclass(frozen=True)
class Task:
    which: str
    description: str

    def __lt__(self, other: Task) -> bool:
        """Sort the instance. For some reason, using ``self.which < other.which`` breaks the sorting..."""
        return self.description.lower() < other.description.lower()


@dataclass
class Location:
    file: str
    line: int
    comment: str

    def __post_init__(self):
        self.line = int(self.line)
        self.comment = self.comment.strip()


@task(
    help={
        "cz": "Run commitizen (cz check) to validate the description of the to-do item as a commit message",
        "valid": "When using cz check, print valid to-do items",
        "invalid": "When using cz check, print invalid to-do items",
        "short": "Short format: only the description, without the lines of code where to-do items were found",
    }
)
def todo(c, cz=False, valid=True, invalid=True, short=False):
    """List to-dos and fix-mes in code. Optionally check if the description follow Conventional Commits (cz check)."""
    all_todos: dict[Task, list[Location]] = defaultdict(list)
    all_keys: list[Task] = []
    for which in ("FIXME", "TODO"):
        # This command freezes if pty=False
        for line in run_lines(c, f"rg --color=never --no-heading {which}", warn=True, pty=True):
            before, after = line.split(which, maxsplit=1)  # type: str,str
            key = Task(which, after.strip(": "))
            all_keys.append(key)
            location = Location(*before.strip("# ").split(":", maxsplit=2))
            all_todos[key].append(location)

    for item, locations in sorted(all_todos.items()):  # type: Task, list[Location]
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

        func(f"{item.which}: {item.description}")

        if short:
            continue
        for loc in locations:  # type: Location
            print(f"   {loc.file}:{loc.line} {loc.comment}")
