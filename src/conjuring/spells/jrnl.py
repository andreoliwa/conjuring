from invoke import task

SHOULD_PREFIX = True


@task
def tags(c, sort=False, rg="", journal=""):
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
def query(c, n=0, contains="", edit=False, fancy=False, short=False, journal=""):
    """Query jrnl entries."""
    format = "pretty"
    if fancy:
        format = "fancy"
    elif short:
        format = "short"

    cmd = ["jrnl"]
    if journal:
        cmd.append(journal)
    if n:
        cmd.append(f"-n {n}")
    cmd.append(f"--format {format}")
    if contains:
        cmd.append(f"-contains {contains}")
    if edit:
        cmd.append("--edit")
    c.run(" ".join(cmd))


@task
def edit_last(c, journal=""):
    """Edit the last jrnl entry."""
    cmd = ["jrnl"]
    if journal:
        cmd.append(journal)
    cmd.append("-1 --edit")
    c.run(" ".join(cmd))
