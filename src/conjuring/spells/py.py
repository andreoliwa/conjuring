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
        return self.context.run("pyenv local").stdout.strip()

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

    def parse_python_version(self, venv: str):
        """For now, assuming we only have Poetry venvs."""
        return venv.split(" ")[0].split("-py")[1]

    def remove_venv(self, python_version: str):
        self.context.run(f"poetry env remove python{python_version}")

    def guess_python_version(self):
        """Guess Python version from pyproject.toml."""
        pyproject_lines = run_lines(
            self.context, f"rg --no-line-number -e '^python ' -e python_version {PYPROJECT_TOML}"
        )
        versions: set[str] = set()
        for line in pyproject_lines:
            clean_version = line.split("=")[1].replace("^", "").replace("~", "").strip('" ')
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

    c.run("poetry install")
