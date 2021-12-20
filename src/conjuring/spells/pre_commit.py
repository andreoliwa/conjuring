from invoke import task

from conjuring.grimoire import run_with_fzf

__CONJURING_PREFIX__ = True


@task
def install(c, gc=False):
    """Pre-commit install scripts and hooks."""
    if gc:
        c.run("pre-commit gc")
    c.run("pre-commit install -t pre-commit -t commit-msg --install-hooks")


@task
def run(c, hook=""):
    """Pre-commit run all hooks or a specific one."""
    if hook:
        chosen_hook = run_with_fzf(c, "yq -r '.repos[].hooks[].id' .pre-commit-config.yaml", query=hook)
    else:
        chosen_hook = ""
    c.run(f"pre-commit run --all-files {chosen_hook}")
