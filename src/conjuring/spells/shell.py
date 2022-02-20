"""Shell tasks."""
from invoke import task

SHOULD_PREFIX = True

COMPAT_DIR = "$BASH_COMPLETION_COMPAT_DIR/"
USER_DIR = "$BASH_COMPLETION_USER_DIR/completions/"
COMPLETION_DIRS = (COMPAT_DIR, USER_DIR)


@task
def completion_list(c):
    """List existing shell completions."""
    for var in COMPLETION_DIRS:
        c.run(f"exa -l {var}")


@task
def completion_install(c, app):
    """Install shell completion. For now, only for the Bash shell, and only for Click projects.

    See:
    - https://click.palletsprojects.com/en/8.0.x/shell-completion/
    - https://github.com/click-contrib/click-completion
    """
    completion_file = f"{COMPAT_DIR}{app}.bash-completion"
    c.run(f"_{app.upper()}_COMPLETE=bash_source {app} > {completion_file}")
    c.run(f"exa -l {completion_file}")
    c.run(f"bat {completion_file}")


@task
def completion_uninstall(c, app):
    """Uninstall shell completion from both completion dirs."""
    for completion_dir in COMPLETION_DIRS:
        with c.cd(completion_dir):
            c.run(f"rm -v {app}*", warn=True)
    completion_list(c)
    return
