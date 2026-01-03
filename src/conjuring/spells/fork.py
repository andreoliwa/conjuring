"""[GitHub](https://github.com/) forks: configure remote and sync."""

from invoke import Context, Exit, task

from conjuring.spells import git

SHOULD_PREFIX = True


@task(
    help={
        "username": "The owner of the original repository. Required",
        "remote": "The remote to sync with (default: upstream)",
    },
)
def remote(c: Context, username: str, remote_: str = "upstream") -> None:
    """[Configure a remote for a fork](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/configuring-a-remote-for-a-fork)."""
    if username.startswith("-"):
        msg = "Arguments should be: username [--remote]"
        raise Exit(msg)
    if not remote_:
        remote_ = username

    project = c.run(r"git remote -v | rg origin | head -1 | rg -o '/(.+)\.git' -r '$1'", pty=False).stdout.strip()
    c.run(f"git remote add {remote_} https://github.com/{username}/{project}.git", warn=True)
    c.run("git remote -v")


@task(help={"remote": "The remote to sync with (default: upstream)"})
def sync(c: Context, remote_: str = "upstream") -> None:
    """[Sync a fork](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/syncing-a-fork)."""
    c.run(f"git fetch {remote_}")
    default_branch = git.set_default_branch(c)
    c.run(f"git rebase {remote_}/{default_branch}")
    c.run("git push")
