"""[MkDocs](https://github.com/mkdocs/mkdocs/) spells: install, build, deploy to GitHub, serve locally."""
from invoke import Context, task

from conjuring.visibility import has_pyproject_toml

SHOULD_PREFIX = True


EXTENSIONS: list[str] = [
    "mkdocs-material",  # https://github.com/squidfunk/mkdocs-material
    "mkdocs-render-swagger-plugin",  # https://github.com/bharel/mkdocs-render-swagger-plugin
    "mkdocstrings[python]",  # https://github.com/mkdocstrings/mkdocstrings
]


@task(help={"force": "Force re-installation of MkDocs."})
def install(c: Context, force: bool = False) -> None:
    """Install MkDocs globally with the Material plugin. Upgrade if it already exists."""
    upgrade = " || pipx upgrade mkdocs" if force else ""
    c.run(f"pipx install mkdocs{upgrade}", warn=True)
    for extension in EXTENSIONS:
        c.run(f"pipx inject mkdocs {extension}")

    # Inject the local project into the global MkDocs installation.
    if has_pyproject_toml():
        c.run("pipx inject mkdocs -e .")


@task
def uninstall(c: Context) -> None:
    """Uninstall MkDocs globally."""
    c.run("pipx uninstall mkdocs")


@task
def build(c: Context) -> None:
    """Build docs."""
    c.run("mkdocs build --strict --verbose --site-dir site")


@task(pre=[build])
def deploy(c: Context) -> None:
    """Deploy docs to GitHub pages."""
    c.run("mkdocs gh-deploy")


@task(pre=[build])
def serve(c: Context) -> None:
    """Start the live-reloading server to test the docs locally."""
    c.run("mkdocs serve")


@task
def browse(c: Context) -> None:
    """Open the static HTML docs website on your browser."""
    c.run("open http://127.0.0.1:8000/")
