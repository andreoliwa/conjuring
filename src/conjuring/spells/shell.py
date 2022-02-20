"""Shell tasks."""
from invoke import task

SHOULD_PREFIX = True


@task
def click_completion(c, app, uninstall=False):
    """Click completion for Bash.

    See:
    - https://click.palletsprojects.com/en/8.0.x/shell-completion/
    - https://github.com/click-contrib/click-completion
    """
    completion_file = f"$BASH_COMPLETION_COMPAT_DIR/{app}.bash-completion"
    if uninstall:
        c.run(f"rm {completion_file}", warn=True)
        c.run("exa -l $BASH_COMPLETION_COMPAT_DIR/")
        return

    c.run(f"_{app.upper()}_COMPLETE=bash_source {app} > {completion_file}")
    c.run(f"exa -l {completion_file}")
