"""[Python](https://www.python.org/) and [Poetry](https://github.com/python-poetry/poetry).

Install venvs, run tests and coverage, install debug tools,
generate [Ruff](https://github.com/charliermarsh/ruff) config.
"""
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Optional

import typer
from invoke import Context, Result, task
from packaging.version import parse

from conjuring.constants import PYPROJECT_TOML
from conjuring.grimoire import print_error, run_command, run_lines, run_with_fzf
from conjuring.visibility import MagicTask, ShouldDisplayTasks, is_poetry_project

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = is_poetry_project

REGEX_RUFF_LINE = re.compile(r"^(?P<filename>.*?):\d+:\d+: (?P<code>.*?)(?P<message> .*)$")
REGEX_RUFF_MESSAGE = re.compile(r"`[^`]+`")


@dataclass
class PyEnv:
    """pyenv-related tasks."""

    context: Context

    def has_local(self) -> bool:
        """Check if a local Python version is set."""
        output = self.context.run("pyenv local", warn=True).stdout.strip()
        return output and "no local version" not in output

    def set_local(self, python_version: str) -> Result:
        """Set the local pyenv version."""
        latest = self.list_versions(python_version)[-1]
        return self.context.run(f"pyenv local {latest}")

    def list_versions(self, python_version: Optional[str] = None) -> list[str]:
        """List all installed Python versions, or only the ones matching the desired version."""
        all_versions = run_lines(self.context, "pyenv versions --bare")
        if not python_version:
            return all_versions

        return [version for version in all_versions if version.startswith(python_version)]


@dataclass()
class Poetry:
    """Poetry-related tasks."""

    context: Context

    def used_in_project(self, display_error: bool = True) -> bool:
        """Check if Poetry is being used."""
        used = int(
            run_command(
                self.context,
                f"grep tool.poetry {PYPROJECT_TOML} 2>/dev/null | wc -c",
                hide=True,
                warn=True,
            ).stdout.strip(),
        )
        if not used and display_error:
            print_error("This task only works with Poetry projects (so far).")
        return bool(used)

    @staticmethod
    def parse_python_version(venv: str) -> str:
        """For now, assuming we only have Poetry venvs."""
        return venv.split(" ")[0].split("-py")[1]

    def remove_venv(self, python_version: str) -> Result:
        """Remove a Poetry venv."""
        return self.context.run(f"poetry env remove python{python_version}")

    def guess_python_version(self) -> str:
        """Guess Python version from pyproject.toml."""
        # TODO: rewrite this hack and use a TOML package to read the values directly
        pyproject_lines = run_lines(
            self.context,
            f"rg --no-line-number -e '^python ' -e python_version {PYPROJECT_TOML}",
        )
        versions: set[str] = set()
        for line in pyproject_lines:
            value_with_comment = line.split("=")[1]
            value_only = value_with_comment.split("#")[0]
            clean_version = value_only.replace("^", "").replace("~", "").strip('" ')
            versions.add(clean_version)
        if len(versions) > 1:
            print_error(f"Multiple Python versions found in {PYPROJECT_TOML}: {versions=}")
            raise SystemExit
        return list(versions)[0]

    def use_venv(self, python_version: str) -> Result:
        """Use a Poetry venv."""
        version_obj = parse(python_version)
        return self.context.run(f"poetry env use python{version_obj.major}.{version_obj.minor}")


class Pytest:
    """Pytest-related tasks."""

    @staticmethod
    def command(s: bool) -> str:
        """Build pytest command."""
        command = "pytest -v"
        if s:
            command += " -s"
        return command


@task(help={"inject": "Pipx repo to inject this project into"})
def editable(c: Context, inject: str = "") -> None:
    """Hack to install a Poetry package as editable until Poetry supports PEP660 hooks.

    It won't be needed anymore when https://github.com/python-poetry/poetry-core/pull/182 is merged.
    """
    if not Poetry(c).used_in_project():
        return

    chosen_repo = ""
    if inject:
        # Ask for the repo before doing anything else... to fail fast if no repo is chosen
        chosen_repo = run_with_fzf(c, "ls -1 ~/.local/pipx/venvs/", query=inject)
        if not chosen_repo:
            return

    c.run("poetry build")
    c.run("tar -xvzf dist/*.gz --strip-components 1 */setup.py")
    # Ignore errors, it might not be installed
    c.run("black setup.py", warn=True)

    if not chosen_repo:
        print_error("Use --inject to inject this repo into a pipx virtualenv.")
        return

    c.run(f"mv {PYPROJECT_TOML} _{PYPROJECT_TOML}")
    run_command(c, "pipx inject -e", chosen_repo, ".")
    c.run(f"mv _{PYPROJECT_TOML} {PYPROJECT_TOML}")
    c.run("rm setup.py")


@task(
    help={
        "version": "Python version",
        "force": "Recreate the environment",
        "delete_all": "Delete all environments",
        "pipx": "Install with pipx",
        "editable": "Install as editable",
    },
)
def install(  # noqa: PLR0913
    c: Context,
    version: str = "",
    force: bool = False,
    delete_all: bool = False,
    pipx: bool = False,
    editable: bool = False,
) -> None:
    """Install a Python virtual environment. For now, only works with Poetry."""
    venv_list = run_lines(c, "poetry env list", hide=False)
    poetry = Poetry(c)
    if not poetry.used_in_project():
        return

    if delete_all:
        for venv_name in venv_list:
            if ".venv" in venv_name:
                c.run("rm -rf .venv")
            else:
                poetry.remove_venv(poetry.parse_python_version(venv_name))

    if not version:
        version = poetry.guess_python_version()
    pyenv = PyEnv(c)
    if force or not pyenv.has_local():
        # TODO: if tox.ini is present in the repo, set all versions from there
        pyenv.set_local(version)
    if force and not delete_all:
        poetry.remove_venv(version)
    poetry.use_venv(version)

    c.run("poetry lock --check && poetry install")
    if pipx:
        run_command(c, "pipx install", "--python", f"python{version}", " --editable" if editable else "", ".")
    c.run("poetry env list")


@task(
    help={
        "s": "Don't capture output (same shortcut as pytest)",
    },
)
def test(c: Context, s: bool = False) -> None:
    """Run tests with pytest."""
    if not Poetry(c).used_in_project():
        return

    run_command(c, "poetry run", Pytest.command(s))


@task
def watch(c: Context) -> None:
    """Watch changed files and run tests with pytest."""
    if not Poetry(c).used_in_project():
        return

    run_command(c, "poetry run", "ptw . --testmon")


@task(
    help={
        "show_all": "Show all lines, even if they are covered",
        "s": "Don't capture output (same shortcut as pytest)",
    },
)
def coverage(c: Context, show_all: bool = False, s: bool = False) -> None:
    """Run tests with pytest and coverage."""
    if not Poetry(c).used_in_project():
        return

    options = [f"--cov={source}" for source in ["src", Path.cwd().name, "app"] if Path(source).exists()]

    skip_option = "" if show_all else ":skip-covered"
    options.append(f"--cov-report=term-missing{skip_option}")

    run_command(c, "poetry run", Pytest.command(s), *options)


@task(
    help={
        "all_": "Install all debug tools",
        "ipython": "Install https://pypi.org/project/ipython/",
        "ipdb": "Install https://pypi.org/project/ipdb/",
        "pudb": "Install https://pypi.org/project/pudb/",
        "icecream": "Install https://pypi.org/project/icecream/",
        "devtools": "Install https://pypi.org/project/devtools/",
        "watch": "Install https://github.com/joeyespo/pytest-watch",
        "watcher": "Install https://github.com/olzhasar/pytest-watcher",
    },
)
def debug_tools(  # noqa: PLR0913
    c: Context,
    all_: bool = False,
    ipython: bool = False,
    ipdb: bool = False,
    pudb: bool = False,
    icecream: bool = False,
    devtools: bool = False,
    watch: bool = False,
    watcher: bool = False,
) -> None:
    """Install debug tools."""
    if not Poetry(c).used_in_project():
        return

    if watch and watcher:
        print_error("Use only one of --watch and --watcher.")
        return
    if watch:
        c.run("poetry run python -m pip uninstall -y pytest-watcher")
    elif watcher:
        c.run("poetry run python -m pip uninstall -y pytest-watch")
    tools = [
        "pip",
        "ipython" if ipython or all_ else "",
        "ipdb" if ipdb or all_ else "",
        "pudb" if pudb or all_ else "",
        "icecream" if icecream or all_ else "",
        "devtools[pygments]" if devtools or all_ else "",
        "pytest-watch pytest-testmon" if watch or all_ else "",
        "pytest-watcher pytest-testmon" if watcher or all_ else "",
    ]
    run_command(c, "poetry run pip install --upgrade", *tools)


@task(klass=MagicTask, help={"url": "Show the URL of the documentation"})
def ruff_config(c: Context, url: bool = False) -> None:
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
