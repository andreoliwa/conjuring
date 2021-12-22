from pathlib import Path

from invoke import task

SHOULD_PREFIX = True


def should_display_tasks() -> bool:
    return Path("pyproject.toml").exists()


@task
def editable(c, inject=True):
    """Hack to install a Poetry package as editable until Poetry supports PEP660 hooks.

    It won't be needed when https://github.com/python-poetry/poetry-core/pull/182 is merged.
    """
    c.run("poetry build")
    c.run("tar -xvzf dist/*.gz --strip-components 1 */setup.py")
    # Ignore errors, it might not be installed
    c.run("black setup.py", warn=True)

    if not inject:
        return
    c.run("mv pyproject.toml _pyproject.toml")
    c.run("pipx inject -e invoke .")
    c.run("mv _pyproject.toml pyproject.toml")
