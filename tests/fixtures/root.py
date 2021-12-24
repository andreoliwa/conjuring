from invoke import task

SHOULD_PREFIX = True


@task
def a(c):
    pass


@task
def b(c):
    pass
