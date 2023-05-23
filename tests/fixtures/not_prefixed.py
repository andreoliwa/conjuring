from invoke import Context, task


@task
def task_c(c: Context) -> None:
    assert c


@task
def task_d(c: Context) -> None:
    assert c
