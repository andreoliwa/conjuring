from invoke import Context, task


@task
def glob_c(c: Context) -> None:
    assert c


@task
def glob_d(c: Context) -> None:
    assert c
