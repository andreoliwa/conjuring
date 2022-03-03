from invoke import task

from conjuring.grimoire import print_error, run_command, run_with_fzf
from conjuring.visibility import ShouldDisplayTasks, is_poetry_project

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = is_poetry_project


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

    c.run("mv pyproject.toml _pyproject.toml")
    run_command(c, "pipx inject -e", chosen_repo, ".")
    c.run("mv _pyproject.toml pyproject.toml")
    c.run("rm setup.py")
