"""Go-related tasks."""

from invoke import Context, task

from conjuring.grimoire import run_command

SHOULD_PREFIX = True


@task
def update_all(c: Context) -> None:
    """Update all Go dependencies."""
    c.run("go get -u ./...")
    c.run("go mod tidy -v")


@task
def clean(c: Context) -> None:
    """Clean Go cache."""
    dry = c.config.run.dry

    run_command(c, "go clean -cache -modcache -i -r", "-n" if dry else "")
