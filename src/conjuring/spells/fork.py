"""[GitHub](https://github.com/) forks: configure remote and sync."""

from invoke import Context, Exit, task

from conjuring.spells.git import Git

SHOULD_PREFIX = True


@task
def remote(c: Context, username: str, remote: str = "") -> None:
    """[Configure a remote for a fork](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/configuring-a-remote-for-a-fork)."""
    if username.startswith("-"):
        msg = "Arguments should be: username [--remote]"
        raise Exit(msg)
    if not remote:
        remote = username

    project = c.run(r"git remote -v | rg origin | head -1 | rg -o '/(.+)\.git' -r '$1'", pty=False).stdout.strip()
    c.run(f"git remote add {remote} https://github.com/{username}/{project}.git", warn=True)
    c.run("git remote -v")


@task
def sync(c: Context, remote: str = "upstream") -> None:
    """[Sync a fork](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/syncing-a-fork)."""
    c.run(f"git fetch {remote}")
    existing_branch = Git(c).checkout("master", "main")
    c.run(f"git merge {remote}/{existing_branch}")
    c.run("git push")
