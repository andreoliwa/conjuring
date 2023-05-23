"""OneDrive: list files with conflicts, ..."""
from __future__ import annotations

from pathlib import Path

import typer
from invoke import Context, task

from conjuring.grimoire import run_lines, run_stdout

SHOULD_PREFIX = True


@task(
    help={"dir": "Directory; can be used multiple times. Default: current dir"},
    iterable=["dir_"],
)
def conflicts(c: Context, dir_: list[str | Path]) -> None:
    """List files with conflicts."""
    if not dir_:
        dir_ = [Path.cwd()]

    hostname = run_stdout(c, "hostname -s").strip()
    suffix = f"-{hostname}"
    for one_dir in list({str(Path(d).expanduser().absolute()) for d in dir_}):
        for line in run_lines(c, f"fd -t f {hostname} {one_dir} | sort"):
            duplicated = Path(line)
            original_name = duplicated.stem[: -len(suffix)]
            original = duplicated.with_stem(original_name)
            typer.echo(run_stdout(c, f"diff {duplicated} {original}", warn=True).strip())
