"""[Ruff](https://github.com/astral-sh/ruff) spells to generate config and remind you of ignored warnings."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from textwrap import dedent

import tomlkit
import typer
from invoke import Context, task
from tomlkit.exceptions import NonExistentKey

from conjuring.constants import PYPROJECT_TOML
from conjuring.grimoire import print_normal, print_success, print_warning, run_lines
from conjuring.visibility import ShouldDisplayTasks, is_poetry_project

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = is_poetry_project

REGEX_RUFF_LINE = re.compile(r"^(?P<filename>.*?):\d+:\d+: (?P<code>.*?)(?P<message> .*)$")
REGEX_RUFF_MESSAGE = re.compile(r"`[^`]+`")


@task(help={"url": "Show the URL of the documentation"})
def config(c: Context, url: bool = False) -> None:
    """Generate ruff configuration from existing warnings."""
    # TODO: feat: check if the global ruff is installed and use it if it is
    ignore: dict[str, set[str]] = defaultdict(set)
    per_file_ignores: dict[str, set[str]] = defaultdict(set)
    for line in run_lines(c, "pre-commit run --all-files ruff", warn=True):
        if line.startswith("warning:"):
            typer.echo(line)
            continue

        match = REGEX_RUFF_LINE.match(line)
        if not match:
            continue

        filename = match.group("filename")
        code = match.group("code")
        message = match.group("message")
        clean_message = REGEX_RUFF_MESSAGE.sub("?", message)

        ignore[code].add(clean_message.strip())
        per_file_ignores[filename].add(code)

    # TODO: edit pyproject.toml existing config for both sections,
    #  skipping existing lines and adding new codes at the bottom
    if ignore:
        header = """
            # https://beta.ruff.rs/docs/settings/#ignore
            ignore = [
                # Ignores to keep
                # TODO: Ignores to fix
        """
        typer.echo(dedent(header).strip())
        _print_ruff_codes(True, ignore, url)
        typer.echo("]\n")

    if per_file_ignores:
        header = """
            # https://beta.ruff.rs/docs/settings/#per-file-ignores
            [tool.ruff.per-file-ignores]
            # Ignores to keep
            # TODO: Ignores to fix
        """
        typer.echo(dedent(header).strip())
        _print_ruff_codes(False, ignore, url)
        for file, codes in sorted(per_file_ignores.items()):
            sorted_codes = '", "'.join(sorted(codes))
            typer.echo(f'"{file}" = ["{sorted_codes}"]')


def _print_ruff_codes(ignore_section: bool, ignore: dict, url: bool) -> None:
    for _code, messages in sorted(ignore.items()):
        joined_messages = ",".join(sorted(messages))
        if ignore_section:
            typer.echo(f'    "{_code}", # {joined_messages}', nl=False)
        else:
            typer.echo(f"# {_code} {joined_messages}", nl=False)
        if url:
            typer.echo(f" https://beta.ruff.rs/docs/rules/?q={_code}")
        else:
            typer.echo()


@task(help={"delete": "Delete the suppressed warnings for the changed files"})
def reminder(c: Context, delete: bool = False) -> None:
    """Remind you of ignored warning that should be fixed on the files you changed on your branch."""
    files = run_lines(
        c,
        "( git whatchanged --name-only --pretty='' origin..HEAD; git status --porcelain | cut -b 4- ) | sort -u",
    )
    if not files:
        print_normal("No files changed on your branch.")
        return

    doc = tomlkit.loads(Path(PYPROJECT_TOML).read_text())
    try:
        per_file_ignores = doc["tool"]["ruff"]["per-file-ignores"]
    except NonExistentKey:
        print_warning(f"No per-file-ignores found on {PYPROJECT_TOML}.")
        return

    dirty = False
    for file in files:
        if file not in per_file_ignores:
            print_success(f"{file}: doesn't have any suppressed warnings")
            continue
        suppressed = per_file_ignores[file]
        if delete:
            del per_file_ignores[file]
            dirty = True
            print_success(f"{file}: suppressed warnings were removed from {PYPROJECT_TOML}: {suppressed}")
        else:
            print_warning(f"{file}: suppressed warnings: {suppressed}")

    if delete and dirty:
        Path(PYPROJECT_TOML).write_text(tomlkit.dumps(doc))
