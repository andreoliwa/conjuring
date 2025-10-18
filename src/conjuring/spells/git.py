"""[Git](https://git-scm.com/): update all, extract subtree, rewrite history, ..."""

from __future__ import annotations

import os.path
import tempfile
from collections import defaultdict
from configparser import ConfigParser
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import typer
from invoke import Context, Exit, UnexpectedExit, task
from slugify import slugify

from conjuring.colors import Color
from conjuring.constants import REGEX_JIRA_TICKET_TITLE
from conjuring.grimoire import (
    REGEX_JIRA,
    print_error,
    print_success,
    print_warning,
    run_command,
    run_lines,
    run_stdout,
    run_with_fzf,
)
from conjuring.visibility import MagicTask, ShouldDisplayTasks, is_git_repo

# keep-sorted start
GLOBAL_GITCONFIG_PATH = Path("~/.gitconfig").expanduser()
GLOBAL_GITIGNORE = "~/.gitignore_global"
SHOULD_PREFIX = True
# keep-sorted end

should_display_tasks: ShouldDisplayTasks = is_git_repo


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
            self.context,
            "git branch -a | rg -o -e /master -e /develop.+ -e /main | sort -u | cut -b 2- | head -1",
        )

    def checkout(self, *branches: str) -> str:
        """Try checking out the specified branches in order."""
        for branch in branches:
            try:
                self.context.run(f"git checkout {branch}")
            except UnexpectedExit:  # noqa: PERF203
                pass
            else:
                return branch
        return ""

    @property
    def github_username(self) -> str:
        """The GitHub username configured in the global settings."""
        return global_config()["github"]["user"]

    def choose_local_branch(self, branch: str) -> str:
        """Choose a local branch."""
        return run_with_fzf(self.context, "git branch --list | rg -v develop | cut -b 3-", query=branch)


@dataclass(frozen=True)
class PrefixBranch:
    """Tuple of prefix and branch name."""

    prefix: str
    branch: str


@task(klass=MagicTask)
def update_all(c: Context, group: str = "") -> None:
    """Run gita super to update and clean branches."""
    parts = ["gita", "super"]
    if group:
        parts.append(group)
    gita_super = " ".join(parts)
    c.run(f"{gita_super} up && {gita_super} delete-merged-branches")


@task
def switch_url_to(c: Context, remote: str = "origin", https: bool = False) -> None:
    """Set an SSH or HTTPS URL for a remote."""
    regex = r"'git@(.+\.com):(.+/.+)\.git\s'" if https else r"'/([^/]+\.com)/([^/]+/.+)\s\('"
    replace = "'$1/$2'" if https else "'$1:$2'"

    result = c.run(f"git remote -v | rg {remote} | head -1 | rg -o {regex} -r {replace}", warn=True, pty=False)
    match = result.stdout.strip()
    if not match:
        typer.echo(f"{Color.BOLD_RED.value}Match not found{Color.NONE.value}")
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
    },
)
def extract_subtree(c: Context, new_project_dir: str, reset: bool = False) -> None:
    """Extract files from subdirectories of the current Git repo to another repo, using git-filter-repo.

    Install https://github.com/newren/git-filter-repo with `pipx install git-filter-repo`.
    """
    new_project_path: Path = Path(new_project_dir).expanduser().resolve().absolute()
    if reset:
        c.run(f"rm -rf {new_project_path}")

    if not new_project_path.exists():
        origin_url = run_stdout(c, "git remote get-url origin")
        c.run(f"git clone {origin_url} {new_project_path}")

    files_and_dirs = set(run_lines(c, Git.SHOW_ALL_FILE_HISTORY, dry=False))
    for line in sorted(files_and_dirs):
        path = Path(line)
        if os.path.sep in line:
            files_and_dirs.add(str(path.parent) + os.path.sep)
            continue

    _, temp_filename = tempfile.mkstemp()
    temp_file = Path(temp_filename)
    try:
        temp_file.write_text(os.linesep.join(sorted(files_and_dirs)))
        chosen_files = set(
            run_with_fzf(
                c,
                f"cat {temp_filename}",
                dry=False,
                header="Use TAB to choose the files you want to copy to the new project",
                multi=True,
                preview="test -f {} && head -20 {} || echo FILE NOT FOUND, IT EXISTS ONLY IN GIT HISTORY",
            ),
        )
    finally:
        temp_file.unlink()

    with c.cd(new_project_dir):
        all_paths = [f"--path '{line}'" for line in sorted(chosen_files)]
        c.run(f"git-filter-repo {' '.join(all_paths)}")
        history(c, full=True)
    print_error("Don't forget to switch to the new repo:", f"  cd {new_project_dir}", join_nl=True)
    print_success(
        "Next steps:",
        "- Run 'invoke git.rewrite' to fix dates and authors",
        "- Create a new empty repo on https://github.com/new without initializing it (no README/.gitignore/license)",
        "- Follow the instructions to add a remote (from 'push an existing repository from the command line')",
        "- Push files to the new repo with:",
        "  git push -u origin master",
        join_nl=True,
    )


@task(
    help={
        "full": "Display all info: files, authors, dates",
        "files": "Display all files in Git history, even the ones that were deleted and don't exist anymore",
        "author": "Display authors",
        "dates": "Display committer and author dates in different colors",
    },
)
def history(c: Context, full: bool = False, files: bool = False, author: bool = False, dates: bool = False) -> None:
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
                typer.echo(
                    "Commit                                   Committer Date            "
                    "Author Date               GPG key          Subject",
                )
                header = False

            fields = line.split("|")
            committer_date = fields[1]
            author_date = fields[2]
            func = print_success if committer_date == author_date else print_error
            func(*fields)
    if not option_chosen:
        msg = "Choose at least one option: --full, --files, --author, --dates"
        raise Exit(msg, 1)


@task(
    help={
        "commit": "Base commit to be used for the range (default: --root)",
        "gpg": "Sign the commit (default: True)",
        "author": "Set the current author (taken from 'git config') on the commit range",
    },
)
def rewrite(c: Context, commit: str = "--root", gpg: bool = True, author: bool = True) -> None:
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
        f' | cut -d" " -f3) git commit --amend --no-edit -n{author_flag}{gpg_flag}\' -i {commit}',
    )
    history(c, dates=True)
    typer.echo()
    typer.echo("NOTE: If commits were modified during the rebase above, their committer date will be the current date")
    typer.echo("Rebase again with this command, without changing any commit, and all dates should be green")


@task
def tidy_up(c: Context) -> None:
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
    },
)
def merge_default(
    c: Context,
    remote: bool = False,
    update: bool = True,
    push: bool = True,
    rebase: bool = False,
) -> None:
    """Merge the default branch of the repo. Also set it with "git config", if not already set."""
    default_branch = set_default_branch(c, remote)

    if update:
        tidy_up(c)
    which_verb = "rebase" if rebase else "merge"
    run_command(c, f"git {which_verb}", f"origin/{default_branch}")
    if push:
        force_option = "--force-with-lease" if rebase else ""
        run_command(c, "git push", force_option)


def set_default_branch(c: Context, remote: bool = False) -> str:
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
        "verbose": "Files: display changes/insertions/deletion."
        " Commits: display the full commit message, author... (default: False)",
        "by_author": "Group commits by author. Doesn't work with --files or --verbose. (default: False)",
    },
)
def changes_since_tag(
    c: Context,
    tag: str = "",
    files: bool = False,
    verbose: bool = False,
    by_author: bool = False,
) -> None:
    """Display changes (commits or files) since the last tag (or a chosen tag)."""
    if files:
        which_tag = tag or run_stdout(c, "git tag --list --sort -creatordate | head -1", hide=False, dry=False)
        default_branch = set_default_branch(c)
        option = "" if verbose else " --name-only"
        c.run(f"git diff --stat {which_tag} origin/{default_branch}{option}")
    else:
        which_tag = tag or "$(git describe --tags --abbrev=0)"
        option = " --format='%aN|%s' | sort -u" if by_author else "" if verbose else " --oneline"
        cmd = f"git log {which_tag}..HEAD{option}"
        if by_author:
            commits_by_author = defaultdict(list)
            for line in run_lines(c, cmd):
                author, commit = line.split("|")
                commits_by_author[author].append(commit)
            for author, commits in commits_by_author.items():
                print(f"\n{author}:")
                for commit in commits:
                    print(f"  {commit}")
        else:
            c.run(cmd)


@task()
def watch(c: Context) -> None:
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
        "original_order": "Don't sort bullets, keep them in original order",
    },
)
def body(c: Context, prefix: bool = False, original_order: bool = False) -> None:
    """Prepare a commit body to be used on pull requests and squashed commits."""
    default_branch = set_default_branch(c)
    bullets = []
    for line in run_lines(c, f"git log {default_branch}..", "--format=%s%n%b"):
        clean = line.strip(" -")
        if (
            "Merge branch" in clean
            or "Merge remote-tracking branch" in clean
            or "Revert " in clean
            or "This reverts" in clean
            or not clean
        ):
            continue

        # Remove Jira ticket with regex
        clean = REGEX_JIRA.sub("", clean).replace("()", "").replace("[]", "").strip(" -")

        # Split on the Conventional Commit prefix
        if not prefix and ":" in clean:
            clean = clean.split(":", 1)[1].strip()

        bullets.append(f"- {clean}")

    results = bullets if original_order else sorted(set(bullets))
    typer.echo("\n".join(results))


@task
def new_branch(c: Context, title: str) -> None:
    """Create a new Git branch with a slugified title while keeping the Jira ticket in uppercase."""
    match = REGEX_JIRA_TICKET_TITLE.match(title)

    if match:
        ticket: str = match.group("ticket")
        title_text: str = match.group("title") or ""
        slugified_title: str = slugify(title_text)
        branch_name: str = f"{ticket}-{slugified_title}" if slugified_title else ticket
    else:
        branch_name = slugify(title)

    typer.echo(f"Creating branch: {branch_name}")
    c.run(f"git checkout -b {branch_name}")


def _find_git_repositories(c: Context, search_dirs: list[Path]) -> set[Path]:
    """Find all Git repositories in the given directories using fd."""
    git_repos = set()
    for search_dir in search_dirs:
        if not search_dir.exists():
            print_warning(f"Directory does not exist: {search_dir}")
            continue

        # Use fd to find .git directories, then get their parent directories
        try:
            # Use fd to find .git directories recursively (need --no-ignore-vcs to see .git dirs)
            lines = run_lines(c, rf"fd -H -t d --no-ignore-vcs '^\.git$' '{search_dir}'", dry=False)
            for line in lines:
                repo_path = Path(line).parent
                git_repos.add(repo_path)
        except Exception as e:  # noqa: BLE001
            print_warning(f"Error searching for Git repos in {search_dir}: {e}")
            continue

    return git_repos


def _is_valid_git_repository(repo_path: Path) -> bool:
    """Check if the given path is a valid Git repository."""
    git_dir: Path = repo_path / ".git"
    return (git_dir / "HEAD").exists() and (git_dir / "refs").exists()


def _count_git_changes(status_lines: list[str]) -> tuple[int, int, int]:
    """Count staged, modified, and untracked files from git status output."""
    modified_count = 0
    untracked_count = 0
    staged_count = 0

    for line in status_lines:
        if len(line) < 2:  # noqa: PLR2004
            continue

        index_status = line[0]  # Staged changes
        worktree_status = line[1]  # Working tree changes

        # Count staged changes
        if index_status in "MADRC":
            staged_count += 1

        # Count working tree changes
        if worktree_status in "MD":
            modified_count += 1
        elif worktree_status == "?":
            untracked_count += 1

    return staged_count, modified_count, untracked_count


def _format_git_status_message(staged_count: int, modified_count: int, untracked_count: int) -> str:
    """Format the git status message for display."""
    status_parts = []
    if staged_count > 0:
        status_parts.append(f"{staged_count} staged")
    if modified_count > 0:
        status_parts.append(f"{modified_count} modified")
    if untracked_count > 0:
        status_parts.append(f"{untracked_count} untracked")

    return ", ".join(status_parts) + " files"


def _check_repository_status(c: Context, repo_path: Path) -> bool:
    """Check if a single repository is dirty and print warning if so.

    Returns:
        True if the repository is dirty, False if clean or invalid.

    """
    try:
        # Change to the repository directory and check status
        with c.cd(str(repo_path)):
            # First verify this is a valid git repository
            if not _is_valid_git_repository(repo_path):
                return False

            # Use git status --porcelain for machine-readable output
            status_lines = run_lines(c, "git status --porcelain", dry=False)

            if not status_lines:
                return False  # Repository is clean

            # Count different types of changes
            staged_count, modified_count, untracked_count = _count_git_changes(status_lines)

            # Build and display status message
            status_message = _format_git_status_message(staged_count, modified_count, untracked_count)
            print_warning(f"Git repo is dirty: {repo_path}, {status_message}")

            return True  # Repository is dirty

    except Exception:  # noqa: BLE001
        # Skip directories that aren't actually git repositories
        # (this can happen if fd finds directories with .git in the name)
        return False


@task(
    help={
        "dir": "Directory to check recursively for dirty repos. Can be used multiple times. Default: current dir",
    },
    iterable=["dir_"],
    klass=MagicTask,
)
def dirty(c: Context, dir_: list[str | Path]) -> bool:
    """Find Git dirs in multiple directories recursively and print the ones which are dirty."""
    # Use current directory if no directories provided
    if not dir_:
        dir_ = [Path.cwd()]

    # Convert to Path objects and expand user paths
    search_dirs = [Path(d).expanduser().resolve() for d in dir_]

    # Find all Git repositories using fd
    git_repos = _find_git_repositories(c, search_dirs)

    if not git_repos:
        print_warning("No Git repositories found")
        return False

    # Check each repository for dirty status
    dirty_repos_found = False
    for repo_path in sorted(git_repos):
        if _check_repository_status(c, repo_path):
            dirty_repos_found = True

    return dirty_repos_found
