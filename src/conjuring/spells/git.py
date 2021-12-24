from pathlib import Path

from conjuring.colors import COLOR_LIGHT_RED, COLOR_NONE
from conjuring.grimoire import run_stdout, run_with_fzf
from invoke import Context, UnexpectedExit, task

from conjuring.visibility import is_git_repo, ShouldDisplayTasks

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = is_git_repo


class Git:
    """Git helpers."""

    def __init__(self, context: Context) -> None:
        self.context = context

    def current_branch(self) -> str:
        """Return the current branch name."""
        return run_stdout(self.context, "git branch --show-current")

    def default_branch(self) -> str:
        """Return the default branch name (master/main/develop/development)."""
        return run_stdout(
            self.context, "git branch -a | rg -o -e /master -e /develop.+ -e /main | sort -u | cut -b 2- | head -1"
        )

    def checkout(self, *branches: str) -> str:
        """Try checking out the specified branches in order."""
        for branch in branches:
            try:
                self.context.run(f"git checkout {branch}")
                return branch
            except UnexpectedExit:
                pass
        return ""

    def choose_local_branch(self, branch: str) -> str:
        return run_with_fzf(self.context, "git branch --list | rg -v develop | cut -b 3-", query=branch)


@task
def fixme(c):
    """Display FIXME comments, sorted by file and with the branch name at the end."""
    cwd = str(Path.cwd())
    c.run(
        fr"rg --line-number -o 'FIXME\[AA\].+' {cwd} | sort -u | sed -E 's/FIXME\[AA\]://'"
        f" | cut -b {len(cwd)+2}- | sed 's/^/{Git(c).current_branch()}: /'"
    )


@task
def update_clean(c, group=""):
    """Run gita super to update and clean branches."""
    parts = ["gita", "super"]
    if group:
        parts.append(group)
    gita_super = " ".join(parts)
    c.run(f"{gita_super} up && {gita_super} delete-merged-branches")


@task
def switch_url_to(c, remote="origin", https=False):
    """Set an SSH or HTTPS URL for a remote."""
    regex = r"'git@(.+\.com):(.+/.+)\.git\s'" if https else r"'/([^/]+\.com)/([^/]+/.+)\s\('"
    replace = "'$1/$2'" if https else "'$1:$2'"

    result = c.run(f"git remote -v | rg {remote} | head -1 | rg -o {regex} -r {replace}", warn=True, pty=False)
    match = result.stdout.strip()
    if not match:
        print(f"{COLOR_LIGHT_RED}Match not found{COLOR_NONE}")
    else:
        repo = f"https://{match}" if https else f"git@{match}.git"
        c.run(f"git remote set-url {remote} {repo}")

    c.run("git remote -v")
