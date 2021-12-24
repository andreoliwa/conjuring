from invoke import task

SHOULD_PREFIX = True


@task
def task_a(c):
    pass


@task
def task_b(c):
    pass
