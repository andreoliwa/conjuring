from pathlib import Path

from invoke import Context, task

from conjuring.grimoire import print_error, run_command, run_lines, run_with_fzf
from conjuring.visibility import ShouldDisplayTasks, is_poetry_project

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = is_poetry_project

PYPROJECT_TOML = "pyproject.toml"


class PyEnv:
    def __init__(self, context: Context) -> None:
        self.context = context

    def has_local(self) -> bool:
        """Check if a local Python version is set."""
        output = self.context.run("pyenv local", warn=True).stdout.strip()
        return output and "no local version" not in output

    def set_local(self, python_version: str):
        """Set the local pyenv version."""
        latest = self.list_versions(python_version)[-1]
        self.context.run(f"pyenv local {latest}")

    def list_versions(self, python_version: str = None):
        """List all installed Python versions, or only the ones matching the desired version."""
        all_versions = run_lines(self.context, "pyenv versions --bare")
        if not python_version:
            return all_versions

        selected_versions = [version for version in all_versions if version.startswith(python_version)]
        return selected_versions


class Poetry:
    def __init__(self, context: Context) -> None:
        self.context = context

    def used_in_project(self, display_error=True) -> bool:
        """Check if Poetry is being used."""
        used = int(
            run_command(
                self.context, f"grep tool.poetry {PYPROJECT_TOML} 2>/dev/null | wc -c", hide=True, warn=True
            ).stdout.strip()
        )
        if not used and display_error:
            print_error("This task only works with Poetry projects (so far).")
        return bool(used)

    def parse_python_version(self, venv: str):
        """For now, assuming we only have Poetry venvs."""
        return venv.split(" ")[0].split("-py")[1]

    def remove_venv(self, python_version: str):
        self.context.run(f"poetry env remove python{python_version}")

    def guess_python_version(self):
        """Guess Python version from pyproject.toml."""
        # TODO: rewrite this hack and use a TOML package to read the values directly
        pyproject_lines = run_lines(
            self.context, f"rg --no-line-number -e '^python ' -e python_version {PYPROJECT_TOML}"
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

    def use_venv(self, python_version: str):
        self.context.run(f"poetry env use python{python_version}")


@task(help={"inject": "Pipx repo to inject this project into"})
def editable(c, inject=""):
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


@task(help={"version": "Python version", "force": "Recreate the environment", "delete_all": "Delete all environments"})
def install(c, version="", force=False, delete_all=False):
    """Install a Python virtual environment. For now, only works with Poetry."""
    venv_list = run_lines(c, "poetry env list", hide=False)
    poetry = Poetry(c)
    if not poetry.used_in_project():
        return

    if delete_all:
        for venv in venv_list:
            poetry.remove_venv(poetry.parse_python_version(venv))

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


@task(help={"watch": "Watch for changes and re-run affected tests. Install pytest-watch and pytest-testmon first."})
def test(c, watch=False):
    """Run tests with pytest."""
    if not Poetry(c).used_in_project():
        return

    command = 'ptw --runner "pytest --testmon"' if watch else "pytest -v"
    run_command(c, "poetry run", command)


@task(help={"show_all": "Show all lines, even if they are covered"})
def coverage(c, show_all=False):
    """Run tests with pytest and coverage."""
    if not Poetry(c).used_in_project():
        return

    options = [f"--cov={source}" for source in ["src", Path.cwd().name, "app"] if Path(source).exists()]

    skip_option = "" if show_all else ":skip-covered"
    options.append(f"--cov-report=term-missing{skip_option}")

    run_command(c, "poetry run pytest -v", *options)


@task(
    help={
        "all_": "Install all debug tools",
        "ipython": "Install https://pypi.org/project/ipython/",
        "ipdb": "Install https://pypi.org/project/ipdb/",
        "pudb": "Install https://pypi.org/project/pudb/",
        "icecream": "Install https://pypi.org/project/icecream/",
        "devtools": "Install https://pypi.org/project/devtools/",
    }
)
def debug_tools(c, all_=False, ipython=False, ipdb=False, pudb=False, icecream=False, devtools=False):
    """Install debug tools."""
    if not Poetry(c).used_in_project():
        return

    tools = [
        "pip",
        "ipython" if ipython or all_ else "",
        "ipdb" if ipdb or all_ else "",
        "pudb" if pudb or all_ else "",
        "icecream" if icecream or all_ else "",
        "devtools[pygments]" if devtools or all_ else "",
    ]
    run_command(c, "poetry run pip install --upgrade", *tools)
