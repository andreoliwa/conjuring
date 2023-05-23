import os

from invoke import Context, task


def should_display_tasks() -> bool:
    return os.environ.get("DISPLAY") == "yes"


@task
def task_e(c: Context) -> None:
    assert c


@task
def task_f(c: Context) -> None:
    assert c
