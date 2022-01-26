from invoke import Exit, task

from conjuring.spells.git import Git

SHOULD_PREFIX = True


@task
def remote(c, username, remote=""):
    """Configure a remote for a fork.

    https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/configuring-a-remote-for-a-fork
    """
    if username.startswith("-"):
        raise Exit("Arguments should be: username [--remote]")
    if not remote:
        remote = username

    project = c.run(r"git remote -v | rg origin | head -1 | rg -o '/(.+)\.git' -r '$1'", pty=False).stdout.strip()
    c.run(f"git remote add {remote} https://github.com/{username}/{project}.git", warn=True)
    c.run("git remote -v")


@task
def sync(c, remote="upstream"):
    """Sync a fork.

    https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/syncing-a-fork
    """
    c.run(f"git fetch {remote}")
    existing_branch = Git(c).checkout("master", "main")
    c.run(f"git merge {remote}/{existing_branch}")
    c.run("git push")
