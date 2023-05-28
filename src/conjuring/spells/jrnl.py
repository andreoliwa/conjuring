"""Query tags and entries with the [jrnl](https://github.com/jrnl-org/jrnl) note-taking tool."""
from invoke import Context, task

SHOULD_PREFIX = True


@task
def tags(c: Context, sort: bool = False, rg: str = "", journal: str = "") -> None:
    """Query jrnl tags."""
    cmd = ["jrnl"]
    if journal:
        cmd.append(journal)
    cmd.append("--tags")
    if sort:
        cmd.append("| sort -u")
    if rg:
        cmd.append(f"| rg {rg}")
    c.run(" ".join(cmd))


@task
def query(  # noqa: PLR0913
    c: Context,
    n: int = 0,
    contains: str = "",
    edit: bool = False,
    fancy: bool = False,
    short: bool = False,
    journal: str = "",
) -> None:
    """Query jrnl entries."""
    format_ = "pretty"
    if fancy:
        format_ = "fancy"
    elif short:
        format_ = "short"

    cmd = ["jrnl"]
    if journal:
        cmd.append(journal)
    if n:
        cmd.append(f"-n {n}")
    cmd.append(f"--format {format_}")
    if contains:
        cmd.append(f"-contains {contains}")
    if edit:
        cmd.append("--edit")
    c.run(" ".join(cmd))


@task
def edit_last(c: Context, journal: str = "") -> None:
    """Edit the last jrnl entry."""
    cmd = ["jrnl"]
    if journal:
        cmd.append(journal)
    cmd.append("-1 --edit")
    c.run(" ".join(cmd))
