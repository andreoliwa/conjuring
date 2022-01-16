from functools import lru_cache
from pathlib import Path

from conjuring.colors import COLOR_LIGHT_RED, COLOR_NONE
from conjuring.grimoire import run_stdout, run_with_fzf, run_lines, run_multiple, print_success, print_error
from invoke import Context, UnexpectedExit, task
from configparser import ConfigParser

from conjuring.visibility import is_git_repo, ShouldDisplayTasks, MagicTask

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = is_git_repo
GLOBAL_GITCONFIG_PATH = Path("~/.gitconfig").expanduser()


class Git:
    """Git helpers."""

    def __init__(self, context: Context) -> None:
        self.context = context

    @lru_cache()
    def global_config(self) -> ConfigParser:
        """Global Git configuration."""
        config = ConfigParser()
        config.read(GLOBAL_GITCONFIG_PATH)
        return config

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

    @property
    def github_username(self) -> str:
        """GitHub user name configured in the global settings."""
        return self.global_config()["github"]["user"]

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


@task(klass=MagicTask)
def update_all(c, group=""):
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


@task(
    help={
        "new_project_dir": "Dir of the project to be created. The dir might exist or not",
        "sub_dir": "Subdir to be extracted from the current project. E.g.: src/my_subdir/",
        "choose_files": "Use fzf to choose files to extract from the subdir",
        "reset": "Remove the new dir and start over",
    }
)
def extract_subtree(c, new_project_dir, sub_dir, choose_files=True, reset=False):
    """Extract files from a subdirectory of the current Git repo to another repo, using git subtree."""
    new_project_path: Path = Path(new_project_dir).expanduser().absolute()
    if reset:
        c.run(f"rm -rf {new_project_path}")

    new_project_path.mkdir(parents=False, exist_ok=True)
    new_project_name = Path(new_project_path).name
    old_project_name = Path.cwd().name
    git = Git(c)
    username = git.github_username

    # Add slash to the end
    absolute_subdir = Path(sub_dir).expanduser().absolute()
    relative_prefix = str(absolute_subdir.relative_to(Path.cwd())).rstrip("/") + "/"

    obliterate = set()
    if choose_files:
        find_cmd = ["fd -H .", str(absolute_subdir)]
        all_files = set(run_lines(c, *find_cmd, dry=False))
        chosen_files = set(
            run_with_fzf(
                c,
                *find_cmd,
                dry=False,
                header="Use TAB to choose the files you want to KEEP",
                multi=True,
                preview="head -10 {+}",
            )
        )
        obliterate = {
            str(Path(kill_file).relative_to(absolute_subdir)) for kill_file in all_files.difference(chosen_files)
        }

    with c.cd(new_project_dir):
        run_multiple(
            c,
            "git init",
            f"git remote add origin git@github.com:{username}/{new_project_name}.git",
            "touch README.md",
            "git add README.md",
            'git commit -m "chore: first commit"',
            f"git remote add -f upstream git@github.com:{username}/{old_project_name}.git",
            "git checkout -b upstream_master upstream/master",
            f"git subtree split --prefix={relative_prefix} -b upstream_subdir",
            "git checkout master",
            "git merge upstream_subdir --allow-unrelated-histories",
            f"git obliterate " + " ".join(sorted(obliterate)) if obliterate else "",
            pty=False,
        )
        history(c)
    print_error("Don't forget to switch to the new repo:", f"  cd {new_project_dir}", nl=True)
    print_success(
        "Next steps:",
        "- Run 'git obliterate' manually for files in Git history (listed above) you still want to remove",
        "- Create a new empty repo on https://github.com/new without initializing it",
        "- Push files to the new repo with:",
        "  git push -u origin master",
        nl=True,
    )


@task(
    help={
        "full": "Display all info: files, authors, dates",
        "files": "Display all files in Git history, even the ones that were deleted and don't exist anymore",
        "author": "Display authors",
        "dates": "Display committer and author dates in different colors",
    }
)
def history(c, full=False, files=False, author=False, dates=False):
    """Grep the whole Git log and display information."""
    if full:
        files = author = dates = True
    if files:
        c.run('git log --pretty="format:" --name-only | sort -u | tail +2')
    if author:
        c.run("git log --name-only | rg author | sort -u")
    if dates:
        header = True
        for line in run_lines(c, 'git log --format="%H|%cI|%aI|%GK|%s"', hide=False):
            if header:
                print_success("Green = dates are equal")
                print_error("Red = dates are different")
                print(
                    "Commit                                   Committer Date            "
                    "Author Date               GPG key          Subject"
                )
                header = False

            fields = line.split("|")
            committer_date = fields[1]
            author_date = fields[2]
            func = print_success if committer_date == author_date else print_error
            func(*fields)


@task
def rebase_sign(c, commit=""):
    """Rebase and GPG sign a range of commits.

    https://git-scm.com/docs/git-commit
    https://git-scm.com/docs/git-rebase
    """
    if not commit:
        commit = "--root"
    c.run(f'git log --format="%H %cI %aI %s" {commit} > $TMPDIR/rebase_sign_hashlist')
    c.run(
        "git rebase --committer-date-is-author-date --exec 'GIT_COMMITTER_DATE="
        '$(fgrep -m 1 "$(git log -1 --format="%aI %s" $GIT_COMMIT)" $TMPDIR/rebase_sign_hashlist'
        f' | cut -d" " -f3) git commit --amend --no-edit -n -S\' -i {commit}'
    )
    history(c, dates=True)
    print()
    print("NOTE: If commits were modified during the rebase above, their committer date will be the current date")
    print("Rebase again with this command, without changing any commit, and all dates should be green")
