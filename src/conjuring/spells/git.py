import re
from configparser import ConfigParser
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from invoke import Context, Exit, UnexpectedExit, task

from conjuring.colors import COLOR_LIGHT_RED, COLOR_NONE
from conjuring.grimoire import (
    print_error,
    print_success,
    run_command,
    run_lines,
    run_multiple,
    run_stdout,
    run_with_fzf,
)
from conjuring.visibility import MagicTask, ShouldDisplayTasks, is_git_repo

SHOULD_PREFIX = True
should_display_tasks: ShouldDisplayTasks = is_git_repo
GLOBAL_GITCONFIG_PATH = Path("~/.gitconfig").expanduser()


@lru_cache
def global_config() -> ConfigParser:
    """Global Git configuration."""
    config = ConfigParser()
    config.read(GLOBAL_GITCONFIG_PATH)
    return config


class Git:
    """Git helpers."""

    # Use "tail +2" to remove the blank line at the top
    SHOW_ALL_FILE_HISTORY = 'git log --pretty="format:" --name-only | sort -u | tail +2'

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

    @property
    def github_username(self) -> str:
        """The GitHub username configured in the global settings."""
        return global_config()["github"]["user"]

    def choose_local_branch(self, branch: str) -> str:
        return run_with_fzf(self.context, "git branch --list | rg -v develop | cut -b 3-", query=branch)


@dataclass(frozen=True)
class PrefixBranch:
    prefix: str
    branch: str


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
        repo = f"https://{match}" if https else f"git@{match}"
        if not repo.endswith(".git"):
            repo += ".git"
        c.run(f"git remote set-url {remote} {repo}")

    c.run("git remote -v")


@task(
    help={
        "new_project_dir": "Dir of the project to be created. The dir might exist or not",
        "reset": "Remove the new dir and start over",
        "keep": "Keep branches and remote after the extracting is done",
    }
)
def extract_subtree(c, new_project_dir, reset=False, keep=False):
    """Extract files from subdirectories of the current Git repo to another repo, using git subtree.

    The files will be moved to the root of the new repo.

    Solutions adapted from:
    - https://serebrov.github.io/html/2021-09-13-git-move-history-to-another-repository.html
    - https://stackoverflow.com/questions/25574407/git-subtree-split-two-directories/58253979#58253979
    """
    new_project_path: Path = Path(new_project_dir).expanduser().absolute()
    if reset:
        c.run(f"rm -rf {new_project_path}")

    new_project_path.mkdir(parents=False, exist_ok=True)
    old_project_path = Path.cwd()

    all_files = set(run_lines(c, Git.SHOW_ALL_FILE_HISTORY, dry=False))
    chosen_files = set(
        run_with_fzf(
            c,
            Git.SHOW_ALL_FILE_HISTORY,
            dry=False,
            header="Use TAB to choose the files you want to KEEP",
            multi=True,
            preview="test -f {} && head -20 {} || echo FILE NOT FOUND, IT EXISTS ONLY IN GIT HISTORY",
        )
    )
    sub_dirs = {part.rsplit("/", 1)[0] for part in chosen_files}
    obliterate = set(all_files.difference(chosen_files))

    first_date = run_stdout(c, 'git log --format="%cI" --root | sort -u | head -1')

    prefixes: list[str] = []
    for sub_dir in sorted(sub_dirs):
        absolute_subdir = Path(sub_dir).expanduser().absolute()
        # Add slash to the end
        prefixes.append(str(absolute_subdir.relative_to(Path.cwd())).rstrip("/") + "/")

    with c.cd(new_project_dir):
        run_multiple(
            c,
            "git init",
            "touch README.md",
            "git add README.md",
            f'git commit -m "chore: first commit" --date {first_date}',
            f"git remote add -f upstream {old_project_path}",
            "git checkout -b upstream_master upstream/master",
            pty=False,
        )
        pairs: set[PrefixBranch] = set()
        for prefix in prefixes:
            if not Path(prefix).exists():
                print_error(f"Skipping non-existent prefix {prefix}...")
                continue

            clean = prefix.strip(" /").replace("/", "_")
            branch = f"upstream_subtree_{clean}"
            local_obliterate = {f[len(prefix) :] for f in obliterate if f.startswith(prefix)}
            pairs.add(PrefixBranch(prefix, branch))

            run_multiple(
                c,
                "git checkout upstream_master",
                f"git subtree split --prefix={prefix} -b {branch}",
                f"git checkout {branch}",
                "git obliterate " + " ".join(sorted(local_obliterate)) if obliterate else "",
                "git checkout master",
                # TODO: fix: deal with files that have the same name in different subdirs
                #  The files are merged in the root, without prefix.
                #  What happens if a file has the same name in multiple subdirs? e.g.: bin/file.py and src/file.py
                f"git merge {branch} --allow-unrelated-histories -m 'refactor: merge subtree {prefix}'",
            )

        if obliterate:
            c.run("git obliterate " + " ".join(sorted(obliterate)))
        if not keep:
            run_multiple(
                c,
                "git branch -D upstream_master",
                *[f"git branch -D {pair.branch}" for pair in pairs],
                "git remote remove upstream",
            )
        history(c, full=True)
    print_error("Don't forget to switch to the new repo:", f"  cd {new_project_dir}", nl=True)
    print_success(
        "Next steps:",
        "- Run 'git obliterate' manually for files in Git history (listed above) you still want to remove",
        "- Run 'invoke git.rewrite' to fix dates and authors",
        "- Create a new empty repo on https://github.com/new without initializing it (no README/.gitignore/license)",
        "- Follow the instructions to add a remote (from 'push an existing repository from the command line')",
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
    option_chosen = False
    if full:
        option_chosen = True
        files = author = dates = True
    if files:
        option_chosen = True
        c.run(Git.SHOW_ALL_FILE_HISTORY)
    if author:
        option_chosen = True
        c.run("git log --name-only | rg author | sort -u")
    if dates:
        option_chosen = True
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
    if not option_chosen:
        raise Exit("Choose at least one option: --full, --files, --author, --dates", 1)


@task(
    help={
        "commit": "Base commit to be used for the range (default: --root)",
        "gpg": "Sign the commit (default: True)",
        "author": "Set the current author (from 'git config') on the commit range",
    }
)
def rewrite(c, commit="--root", gpg=True, author=True):
    """Rewrite a range of commits, signing with GPG and setting the author.

    https://git-scm.com/docs/git-commit
    https://git-scm.com/docs/git-rebase
    """
    gpg_flag = " --gpg-sign" if gpg else " --no-gpg-sign"

    author_flag = ""
    if author:
        name = run_stdout(c, "git config user.name", dry=False)
        email = run_stdout(c, "git config user.email", dry=False)
        author_flag = f' --author "{name} <{email}>"'

    c.run(f'git log --format="%H %cI %aI %s" {commit} > $TMPDIR/rebase_sign_hashlist')
    c.run(
        "git rebase --committer-date-is-author-date --exec 'GIT_COMMITTER_DATE="
        '$(fgrep -m 1 "$(git log -1 --format="%aI %s" $GIT_COMMIT)" $TMPDIR/rebase_sign_hashlist'
        f' | cut -d" " -f3) git commit --amend --no-edit -n{author_flag}{gpg_flag}\' -i {commit}'
    )
    history(c, dates=True)
    print()
    print("NOTE: If commits were modified during the rebase above, their committer date will be the current date")
    print("Rebase again with this command, without changing any commit, and all dates should be green")


@task
def tidy_up(c):
    """Prune remotes, update all branches of the repo, delete merged/squashed branches."""
    c.run("gitup .")
    c.run("git delete-merged-branches")

    # warn=True is needed; apparently, this command fails when there is no branch, and execution is stopped
    c.run("git delete-squashed-branches", warn=True)

    for remote in run_lines(c, "git remote", dry=False):
        c.run(f"git remote prune {remote}")


@task(
    help={
        "remote": "List remote branches (default: False)",
        "update": "Update the repo before merging (default: True)",
        "push": "Push the merge to the remote (default: True)",
        "rebase": "Rebase the default branch before merging (default: False)",
    }
)
def merge_default(c, remote=False, update=True, push=True, rebase=False):
    """Merge the default branch of the repo. Also set it with "git config", if not already set."""
    default_branch = set_default_branch(c, remote)

    if update:
        tidy_up(c)
    which_verb = "rebase" if rebase else "merge"
    run_command(c, f"git {which_verb}", f"origin/{default_branch}")
    if push:
        force_option = "--force-with-lease" if rebase else ""
        run_command(c, "git push", force_option)


def set_default_branch(c: Context, remote=False):
    """Set the default branch config on the repo, if not configured yet."""
    cmd_read_default_branch = "git config git-extras.default-branch"
    default_branch = run_stdout(c, cmd_read_default_branch, warn=True, dry=False)
    if not default_branch:
        default_branch = run_with_fzf(
            c,
            "git branch --list",
            "--all" if remote else "",
            "| cut -b 3- | grep -v HEAD | sed -E 's#remotes/[^/]+/##g' | sort -u",
        )
        run_command(c, cmd_read_default_branch, default_branch)
        run_command(c, "git config init.defaultBranch", default_branch)
        run_command(c, "git config --list | rg default.*branch")
    return default_branch


@task(
    help={
        "tag": "Name of the tag to compare to (default: last created tag)",
        "files": "Display files instead of commits (default: false)",
        "verbose": "Files: display changes/insertions/deletion. Commits: display the full commit message, author... (default: False)",
    }
)
def changes_since_tag(c, tag="", files=False, verbose=False):
    """Display changes (commits or files) since the last tag (or a chosen tag)."""
    which_tag = tag or run_stdout(c, "git tag --list --sort -creatordate | head -1", hide=False, dry=False)
    default_branch = set_default_branch(c)
    if files:
        option = "" if verbose else " --name-only"
        c.run(f"git diff --stat {which_tag} origin/{default_branch}{option}")
    else:
        option = "" if verbose else " --oneline"
        c.run(f"git log {which_tag}..origin/{default_branch}{option}")


@task()
def watch(c):
    """Watch a build on GitHub Actions, then open a pull request or repo after the build is over."""
    current_branch = Git(c).current_branch()
    print_success(f"Current branch = {current_branch}")

    c.run("gh run watch", warn=True)
    out = c.run(f"gh pr view {current_branch} --web", warn=True).stdout.strip()
    if "no pull requests found for branch" in out:
        c.run("gh repo view --web")


@task(
    help={
        "prefix": "Keep the Conventional Commits prefix",
        "sort": "Sort bullets",
    }
)
def body(c, prefix=True, sort=True):
    """Prepare a commit body to be used on pull requests and squashed commits."""
    default_branch = set_default_branch(c)
    bullets = []
    for line in run_lines(c, f"git log {default_branch}..", "--format=%s%n%b"):
        clean = line.strip(" -")
        if "Merge branch" in clean or "Revert " in clean or "This reverts" in clean or not clean:
            continue

        # Split on the Conventional Commit prefix
        if not prefix and ":" in clean:
            clean = clean.split(":", 1)[1]

        # Remove Jira ticket with regex
        clean = re.sub(r"\[?\D+-\d+[\]:]", "", clean).strip(" -")

        bullets.append(f"- {clean}")

    results = sorted(set(bullets)) if sort else bullets
    print("\n".join(results))
