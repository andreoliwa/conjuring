"""MkDocs: install, build, deploy to GitHub, serve locally. https://github.com/mkdocs/mkdocs/."""
from invoke import Context, task

SHOULD_PREFIX = True


@task
def install(c: Context) -> None:
    """Install MkDocs globally with the Material plugin. Upgrade if it already exists."""
    c.run("pipx install mkdocs || pipx upgrade mkdocs")
    c.run("pipx inject mkdocs mkdocs-material mkdocs-render-swagger-plugin")


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
