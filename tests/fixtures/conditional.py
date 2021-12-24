import os

from invoke import task


def should_display_tasks() -> bool:
    return os.environ.get("DISPLAY") == "yes"


@task
def task_e(c):
    pass


@task
def task_f(c):
    pass
