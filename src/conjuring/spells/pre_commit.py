from invoke import task

from conjuring.grimoire import run_with_fzf, run_command

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
    chosen_hook = run_with_fzf(c, "yq e '.repos[].hooks[].id' .pre-commit-config.yaml", query=hook) if hook else ""
    c.run(f"pre-commit run --all-files {chosen_hook}")


@task()
def auto(c, repo="", bleed=False):
    """Autoupdate a Git hook or all hooks with the latest tag."""
    command = ""
    if repo:
        chosen = run_with_fzf(c, "yq e '.repos[].repo' .pre-commit-config.yaml", query=repo, dry=False)
        command = f"--repo {chosen}"
    run_command(c, "pre-commit autoupdate", "--bleeding-edge" if bleed else "", command)
