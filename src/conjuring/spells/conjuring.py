from pathlib import Path

from invoke import task

from conjuring.grimoire import run_command
from conjuring.visibility import ShouldDisplayTasks, is_home_dir

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = is_home_dir


@task(
    help={
        "edit": "Open the config file with $EDITOR",
        "revert": "Revert the changes and go back to using tasks.py as the default tasks file",
    }
)
def setup(c, edit=False, revert=False):
    """Setup Conjuring on your home dir."""
    config_file = Path("~/.invoke.yaml").expanduser()
    json_config = """'{"tasks":{"collection_name":"conjuring_summon"}}'"""
    if config_file.exists():
        message = "Remove this from" if revert else "Add this to"
        print(f"The {config_file} configuration file already exists! {message} the file:")
        run_command(c, "yq eval -n", json_config)
        if edit:
            run_command(c, "$EDITOR", str(config_file))
    else:
        if not revert:
            c.run(f"touch {config_file}")
            run_command(c, "yq eval -i", json_config, str(config_file))
            c.run(f"cat {config_file}")

    default_tasks = Path("~/tasks.py").expanduser()
    conjuring_tasks = Path("~/conjuring_summon.py").expanduser()
    if revert:
        if conjuring_tasks.exists():
            conjuring_tasks.rename(default_tasks)
    else:
        if default_tasks.exists():
            default_tasks.rename(conjuring_tasks)
