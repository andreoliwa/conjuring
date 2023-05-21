from pathlib import Path

from invoke import task

from conjuring.constants import CONJURING_INIT, INVOKE_YAML
from conjuring.grimoire import print_success, print_warning, run_command, run_stdout

SHOULD_PREFIX = True


@task(
    help={
        "edit": "Open the config file with $EDITOR",
        "revert": "Revert the changes and go back to using tasks.py as the default tasks file",
    },
)
def init(c, edit=False, revert=False):
    """Init Conjuring on your home dir to merge any local `tasks.py` file with global Conjuring tasks."""
    config_file = INVOKE_YAML

    json_config = f"""'{{"tasks":{{"collection_name":"{CONJURING_INIT}"}}'"""
    if config_file.exists():
        current_collection_name = run_stdout(c, f"yq e '.tasks.collection_name' {config_file}")
        if current_collection_name == CONJURING_INIT:
            print_success(f"Configuration file is already set to {CONJURING_INIT!r}")
            run_command(c, f"cat {config_file}")
        else:
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
    conjuring_init = Path(f"~/{CONJURING_INIT}.py").expanduser()
    if revert:
        if conjuring_init.exists():
            conjuring_init.rename(default_tasks)
    else:
        if default_tasks.exists():
            default_tasks.rename(conjuring_init)
        else:
            if conjuring_init.exists():
                print_success("Global tasks file already exists.")
                run_command(c, f"cat {conjuring_init}")
            else:
                print_warning(f"Nothing to do: file {default_tasks} does not exist!")
