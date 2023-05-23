from invoke import Context, task

SHOULD_PREFIX = True


@task
def a(c: Context) -> None:
    assert c


@task
def b(c: Context) -> None:
    assert c
