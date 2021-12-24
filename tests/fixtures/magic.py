import os

from invoke import task

from conjuring.visibility import MagicTask


def should_display_tasks() -> bool:
    return os.environ.get("INDIVIDUAL") == "yes"


@task
def depends_on_the_module_config(c):
    pass


@task(klass=MagicTask)
def this_task_is_always_visible(c):
    pass
