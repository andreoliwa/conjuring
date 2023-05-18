"""MkDocs tasks."""
from invoke import task

SHOULD_PREFIX = True


@task
def install(c):
    """Install MkDocs globally with the Material plugin. Upgrade if it already exists."""
    c.run("pipx install mkdocs || pipx upgrade mkdocs")
    c.run("pipx inject mkdocs mkdocs-material mkdocs-render-swagger-plugin")


@task
def build(c):
    """Build docs."""
    c.run("mkdocs build --strict --verbose --site-dir site")


@task(pre=[build])
def deploy(c):
    """Deploy docs to GitHub pages."""
    c.run("mkdocs gh-deploy")


@task
def serve(c):
    """Start the live-reloading server to test the docs locally."""
    c.run("mkdocs serve")


@task
def browse(c):
    """Open the static HTML docs website on your browser."""
    c.run("open http://127.0.0.1:8000/")
