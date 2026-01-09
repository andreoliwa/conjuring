"""[Git](https://git-scm.com/): update all, extract subtree, rewrite history, ..."""

from __future__ import annotations

import os.path
import tempfile
import time
from collections import defaultdict
from configparser import ConfigParser
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from invoke import Context, UnexpectedExit, task
from rich.console import Console
from rich.table import Table
from slugify import slugify
from tqdm import tqdm

if TYPE_CHECKING:
    from collections.abc import Generator

from conjuring.colors import Color
from conjuring.constants import REGEX_JIRA_TICKET_TITLE
from conjuring.grimoire import (
    REGEX_JIRA,
    ask_yes_no,
    print_error,
    print_success,
    print_warning,
    run_command,
    run_lines,
    run_stdout,
    run_with_fzf,
    vanish,
)
from conjuring.visibility import MagicTask, ShouldDisplayTasks, is_git_repo

# keep-sorted start
DOT_GIT = ".git"
GLOBAL_GITCONFIG_PATH = Path("~/.gitconfig").expanduser()
GLOBAL_GITIGNORE = "~/.gitignore_global"
IMPORT_REPOS_TAG_PREFIX = "before-import-repos"
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

    READ_DEFAULT_BRANCH = "git config git-extras.default-branch"

    def __init__(self, context: Context) -> None:
        self.context = context

    def current_branch(self) -> str:
        """Return the current branch name."""
        return run_stdout(self.context, "git branch --show-current")

    def default_branch(self) -> str:
        """Return the default branch nam as configured in git-extras.default-branch, if available."""
        return run_stdout(self.context, Git.READ_DEFAULT_BRANCH, warn=True, dry=False)

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


@dataclass(frozen=True)
class GitChanges:
    """Git repository change counts."""

    staged: int
    modified: int
    untracked: int


@dataclass(frozen=True)
class RepoDirtyStatus:
    """Status of a dirty Git repository."""

    repo_path: Path
    staged: int
    modified: int
    untracked: int
    stashes: int


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
        if not repo.endswith(DOT_GIT):
            repo += DOT_GIT
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

    This function extracts a subset of files from the current repository's entire Git history into a new
    repository, preserving all commits that touched those files.

    Steps:
    1. Prepare new project directory (clone from origin or reset if requested)
    2. Gather all files from Git history including deleted files
    3. Interactive selection with fzf (TAB to select/deselect)
    4. Filter repository history using git-filter-repo with selected paths
    5. Display next steps and instructions

    Prerequisites:
    - Install git-filter-repo: `pipx install git-filter-repo`
    - Current directory must be a Git repository with a remote origin

    Warning:
    - Rewrites Git history in the new repository
    - Do NOT push filtered repository to the same remote as the original

    """
    new_project_path = _resolve_repo_path(new_project_dir)
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
        vanish(msg, 1)


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
        c.run("git pull")
    which_verb = "rebase" if rebase else "merge"
    run_command(c, f"git {which_verb}", f"origin/{default_branch}")
    if push:
        force_option = "--force-with-lease" if rebase else ""
        run_command(c, "git push", force_option)


def set_default_branch(c: Context, remote: bool = False) -> str:
    """Set the default branch config on the repo, if not configured yet."""
    branch = Git(c).default_branch()
    if not branch:
        branch = run_with_fzf(
            c,
            "git branch --list",
            "--all" if remote else "",
            "| cut -b 3- | grep -v HEAD | sed -E 's#remotes/[^/]+/##g' | sort -u",
        )
        run_command(c, Git.READ_DEFAULT_BRANCH, branch)
        run_command(c, "git config init.defaultBranch", branch)
        run_command(c, "git config --list | rg default.*branch")
    return branch


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


def _find_git_repositories_streaming(c: Context, search_dirs: list[Path]) -> Generator[Path, None, None]:
    """Find Git repositories and yield them as they're discovered.

    This streaming version allows processing to start immediately without waiting
    for all repositories to be found first.

    Yields:
        Path: Repository path as it's discovered

    """
    seen_repos = set()
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
                if repo_path not in seen_repos:
                    seen_repos.add(repo_path)
                    yield repo_path
        except Exception as e:  # noqa: BLE001
            print_warning(f"Error searching for Git repos in {search_dir}: {e}")
            continue


def is_valid_git_repository(repo_path: Path) -> bool:
    """Check if the given path is a valid Git repository."""
    git_dir: Path = repo_path / DOT_GIT
    return (git_dir / "HEAD").exists() and (git_dir / "refs").exists()


def _resolve_repo_path(path: str | Path) -> Path:
    """Resolve and normalize a repository path.

    Args:
        path: Path string or Path object to resolve

    Returns:
        Resolved absolute Path object

    """
    return Path(path).expanduser().resolve().absolute()


def _validate_git_repo(repo_path: Path, repo_name: str = "Repository") -> None:
    """Validate that a path exists and is a Git repository.

    Args:
        repo_path: Path to validate
        repo_name: Name to use in error messages (e.g., "Target repository", "Source repository")

    Raises:
        SystemExit: If path doesn't exist or is not a Git repository

    """
    if not repo_path.exists():
        vanish(f"{repo_name} does not exist: {repo_path}")
    if not is_valid_git_repository(repo_path):
        vanish(f"{repo_name} is not a Git repository: {repo_path}")


def _count_git_changes(status_lines: list[str]) -> GitChanges:
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

    return GitChanges(staged=staged_count, modified=modified_count, untracked=untracked_count)


def _is_repo_dirty(c: Context, repo_path: Path) -> RepoDirtyStatus | None:
    """Check if a single repository is dirty.

    Returns:
        RepoDirtyStatus if dirty, None if clean or invalid.

    """
    try:
        # Change to the repository directory and check status
        with c.cd(str(repo_path)):
            # First verify this is a valid git repository
            if not is_valid_git_repository(repo_path):
                return None

            # Use git status --porcelain for machine-readable output
            status_lines = run_lines(c, "git status --porcelain", dry=False)

            # Count different types of changes
            changes = _count_git_changes(status_lines)

            # Check for stashed code
            stash_count = int(run_stdout(c, "git stash list | wc -l", dry=False))

            # Return data if repository is dirty
            if changes.staged > 0 or changes.modified > 0 or changes.untracked > 0 or stash_count > 0:
                return RepoDirtyStatus(
                    repo_path=repo_path,
                    staged=changes.staged,
                    modified=changes.modified,
                    untracked=changes.untracked,
                    stashes=stash_count,
                )

            return None

    except Exception:  # noqa: BLE001
        # Skip directories that aren't actually git repositories
        # (this can happen if fd finds directories with .git in the name)
        return None


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

    # Collect repositories as they're found and check them immediately
    dirty_repos_data = []
    all_repos = []

    # Use streaming approach: process repos as they're discovered
    # This makes the progress bar appear immediately
    with tqdm(desc="Finding dirty repositories", unit=" repos") as pbar:
        for repo_path in _find_git_repositories_streaming(c, search_dirs):
            all_repos.append(repo_path)
            pbar.set_postfix_str(str(repo_path))
            repo_data = _is_repo_dirty(c, repo_path)
            if repo_data:
                dirty_repos_data.append(repo_data)
            pbar.update(1)

    if not all_repos:
        print_warning("No Git repositories found")
        return False

    if not dirty_repos_data:
        print_warning("No dirty repositories found")
        return False

    # Create and display Rich table
    table = Table(title="Dirty Git Repositories", show_header=True, header_style="bold magenta")
    table.add_column("Repository", style="cyan", no_wrap=False)
    table.add_column("Staged", justify="right")
    table.add_column("Modified", justify="right")
    table.add_column("Untracked", justify="right")
    table.add_column("Stashes", justify="right")

    for repo_status in dirty_repos_data:
        # Helper function to format counts (empty string for zero)
        def format_count(count: int) -> str:
            return str(count) if count > 0 else ""

        table.add_row(
            str(repo_status.repo_path),
            format_count(repo_status.staged),
            format_count(repo_status.modified),
            format_count(repo_status.untracked),
            format_count(repo_status.stashes),
        )

    # Print the table using rich
    console = Console()
    console.print(table)

    return True


def _handle_rollback(c: Context, target_path: Path) -> None:
    """Handle rollback mode for import_repos.

    Args:
        c: Invoke context
        target_path: Path to the target repository

    Raises:
        SystemExit: If rollback is aborted or no tags found

    """
    _validate_git_repo(target_path, "Target directory")

    with c.cd(str(target_path)):
        safety_tags = run_lines(c, f"git tag -l '{IMPORT_REPOS_TAG_PREFIX}-*'", dry=False)
        if not safety_tags:
            vanish(f"No safety tags found (tags starting with '{IMPORT_REPOS_TAG_PREFIX}-')")

        try:
            chosen_tag = run_with_fzf(
                c,
                f"git tag -l '{IMPORT_REPOS_TAG_PREFIX}-*'",
                dry=False,
                header="Select a safety tag to rollback to",
            )
        except Exception:  # noqa: BLE001
            vanish("Rollback aborted, no tag was selected")

        if not chosen_tag:
            vanish("Rollback aborted, no tag was selected")

        ask_yes_no(f"Are you sure you want to rollback to tag {chosen_tag}?")

        print_success(f"Rolling back to tag: {chosen_tag}")
        c.run(f"git reset --hard {chosen_tag}")

        c.run(f"git tag -d {chosen_tag}")
        print_success(f"Deleted safety tag: {chosen_tag}")

        print_success("Remaining tags:")
        c.run("git tag")


def _validate_and_display_repo_status(
    c: Context,
    repo_path: Path,
    repo_label: str,
    show_branches: bool = False,
) -> str:
    """Validate a repository and display its status.

    Args:
        c: Invoke context
        repo_path: Path to the repository
        repo_label: Label for display (e.g., "Target repository", "Source repository")
        show_branches: Whether to show all branches

    Returns:
        Current branch name

    """
    with c.cd(str(repo_path)):
        current_branch = Git(c).current_branch()

    print_success(f"{repo_label}: {repo_path} (current branch: {current_branch})")

    if show_branches:
        with c.cd(str(repo_path)):
            c.run("git branch -a")

    dirty(c, [repo_path])

    return current_branch


def _perform_repo_merge(
    c: Context,
    target_path: Path,
    src_path: Path,
    src_branch: str,
    dir_: str,
) -> None:
    """Perform the actual repository merge operation.

    Args:
        c: Invoke context
        target_path: Path to target repository
        src_path: Path to source repository
        src_branch: Branch name from source repository to merge
        dir_: Destination directory name in target repository

    """
    temp_dir = Path(tempfile.mkdtemp(prefix="git-import-repos-"))
    try:
        print_success(f"\nMerging {src_path.name} (branch: {src_branch}) into {dir_}/ ...")

        temp_clone = temp_dir / dir_
        print(f"Creating a fresh clone at {temp_clone} (required by git-filter-repo)...")
        # Use --no-local to avoid hardlinks which git-filter-repo refuses to work with
        c.run(f"git clone --no-local {src_path} {temp_clone}")

        with c.cd(str(temp_clone)):
            print(f"Rewriting history to move everything into the subdirectory {dir_}/ ...")
            c.run(f"git checkout {src_branch}")
            c.run(f"git filter-repo --force --to-subdirectory-filter {dir_}")

        remote_name = f"temp-import-{dir_}"
        with c.cd(str(target_path)):
            print("Adding temporary remote and fetching...")
            c.run(f"git remote add {remote_name} {temp_clone}")
            c.run(f"git fetch {remote_name}")

            print(f"Merging {dir_} history...")
            merge_msg = f"chore(git): merge repository {src_path} into subdir {dir_!r}"
            c.run(f'git merge --allow-unrelated-histories -m "{merge_msg}" {remote_name}/{src_branch}')

            print("Cleaning up temporary remote...")
            c.run(f"git remote remove {remote_name}")

        print_success(f"Successfully merged {dir_}")
    finally:
        print(f"\nCleaning up temporary clone at {temp_dir}...")
        c.run(f"rm -rf {temp_dir}")


@task(
    help={
        "target": "Path to the target repository where source repo will be merged into",
        "source": "Path to source repository to merge",
        "dir_": "Name of the destination directory in the target repository (default: source repo name)",
        "yes": "Skip confirmation prompt and proceed automatically",
        "rollback": "Rollback a previous import by selecting a safety tag",
    },
)
def import_repos(  # noqa: PLR0913
    c: Context,
    target: str,
    source: str = "",
    dir_: str = "",
    yes: bool = False,
    rollback: bool = False,
) -> None:
    """Merge a Git repository into a target repository as a subdirectory, preserving history.

    This function safely merges a source repository into a target repository locally, without pushing
    any changes. All operations are Git-reversible using standard Git commands.

    The current branch of the source repository will be used for the merge.
    If the destination directory is not specified, the source repository name will be used.

    Detailed steps:
    1. Validate repositories and check that destination directory doesn't exist
    2. Create a temporary clone of the source repository
    3. Rewrite the temporary clone's history to move all files into the destination subdirectory
    4. Add the rewritten repository as a temporary remote and fetch it
    5. Merge the unrelated histories into the target repository
    6. Clean up temporary remote and clone directory
    7. Display rollback instructions

    Prerequisites:
    - Install git-filter-repo: pipx install git-filter-repo
    - Target repository must exist and be a Git repository
    - Source repository must exist and be a Git repository

    Safety features:
    - No git push commands - all changes are local only
    - Source repository is never modified (temporary clone is used)
    - Target repository can be rolled back using git reset
    - Creates a tag before merging for easy rollback

    Note: git-extras has a git-merge-repo command, but I only found out about it after I had written
    this function, which does a lot of verifications that git-merge-repo doesn't.

    Example usage:
      invoke git.import-repos --target=/path/to/target --source=/path/to/source --dir_=my-subdir
      invoke git.import-repos --source=/path/to/source  # Uses source repo name as destination dir

    Rollback:
      invoke git.import-repos --target=/path/to/target --rollback

    """
    if rollback:
        target_path = _resolve_repo_path(target) if target else Path.cwd()
        _handle_rollback(c, target_path)
        return

    if not source:
        vanish("Source repository must be specified using --source")

    target_path = _resolve_repo_path(target) if target else Path.cwd()
    _validate_git_repo(target_path, "Target repository")

    src_path = _resolve_repo_path(source)
    _validate_git_repo(src_path, "Source repository")

    if not dir_:
        dir_ = src_path.name
    dest_dir_path = target_path / dir_
    if dest_dir_path.exists():
        vanish(f"The destination dir {dir_!r} already exists")

    _validate_and_display_repo_status(c, target_path, "Target repository")
    print_success(f"Destination directory: {dir_}")
    src_branch = _validate_and_display_repo_status(c, src_path, "Source repository", show_branches=True)

    if not yes:
        ask_yes_no("Do you want to proceed with merging this repository?")

    timestamp = time.strftime("%Y-%m-%d-%H-%M-%S")
    safety_tag = f"{IMPORT_REPOS_TAG_PREFIX}-{timestamp}"
    tag_message = f"Before merging repo {src_path.name} into {target_path.name}/{dir_}"

    with c.cd(str(target_path)):
        c.run(f"git tag -a {safety_tag} -m '{tag_message}'")
        print_success(f"Created safety tag: {safety_tag}")

    _perform_repo_merge(c, target_path, src_path, src_branch, dir_)

    with c.cd(str(target_path)):
        c.run("git log -1")

    print_success("\nRepository merged successfully!")
    print("\nRollback option if needed:")
    target_flag = f" --target={target_path}" if target else ""
    print(f"  invoke git.import-repos{target_flag} --rollback")
    print("\nOr manually:")
    print(f"  cd {target_path} && git reset --hard {safety_tag}")
    print("\nTo keep the changes, you can delete the safety tag:")
    print(f"  cd {target_path} && git tag -d {safety_tag}")
    print_warning("\nRemember: No changes have been pushed. Run 'git push' when ready.")
    print("\nNote: Source repository was not modified (temporary clone was used).")
