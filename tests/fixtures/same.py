from invoke import Context, task


@task
def task_c(c: Context) -> None:
    assert c
