from invoke import Context, task

SHOULD_PREFIX = True


@task
def task_a(c: Context) -> None:
    assert c


@task
def task_b(c: Context) -> None:
    assert c
