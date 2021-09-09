"""Load invoke tasks for the home directory and from the current dir.

Helpful docs:
- http://www.pyinvoke.org/
- http://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run
"""
import os
import sys
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import List, Set

from invoke import Collection, Context, UnexpectedExit, task
from invoke.exceptions import Exit

COLOR_NONE = "\033[0m"
COLOR_CYAN = "\033[36m"
COLOR_LIGHT_GREEN = "\033[1;32m"
COLOR_LIGHT_RED = "\033[1;31m"

CONJURING_IGNORE_MODULES = os.environ.get("CONJURING_IGNORE_MODULES", "").split(",")
M3_PICTURES = Path("/Volumes/m3/backup/Pictures")


def join_pieces(*pieces: str):
    """Join pieces, ignoring empty strings."""
    return " ".join(piece for piece in pieces if piece.strip())


def run_command(c: Context, *pieces: str, warn=False):
    """Build command from pieces, ignoring empty strings."""
    return c.run(join_pieces(*pieces), warn=warn)


def run_stdout(c: Context, *pieces: str, hide=True) -> str:
    """Run a (hidden) command and return the stripped stdout."""
    return c.run(join_pieces(*pieces), hide=hide, pty=False).stdout.strip()


def run_lines(c: Context, *pieces: str) -> List[str]:
    """Run a (hidden) command and return the result as lines."""
    return run_stdout(c, *pieces).splitlines()


def print_error(*message: str):
    """Print an error message."""
    all_messages = " ".join(message)
    print(f"{COLOR_LIGHT_RED}{all_messages}{COLOR_NONE}")


def run_with_fzf(c: Context, *pieces: str, query="") -> str:
    """Run a command with fzf and return the chosen entry."""
    fzf_pieces = ["| fzf --reverse --select-1 --height 40%"]
    if query:
        fzf_pieces.append(f"-q '{query}'")
    return run_stdout(c, *pieces, *fzf_pieces, hide=False)


class Git:
    """Git helpers."""

    CMD_LOCAL_BRANCHES = "git branch --list | rg -v develop | cut -b 3-"

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


@task
def fixme(c):
    """Display FIXME comments, sorted by file and with the branch name at the end."""
    cwd = str(Path.cwd())
    c.run(
        fr"rg --line-number -o 'FIXME\[AA\].+' {cwd} | sort -u | sed -E 's/FIXME\[AA\]://'"
        f" | cut -b {len(cwd)+2}- | sed 's/^/{Git(c).current_branch()}: /'"
    )


@task
def super_up_bclean(c, group=""):
    """Run gita super to update and clean branches."""
    parts = ["gita", "super"]
    if group:
        parts.append(group)
    cmd = " ".join(parts)
    c.run(f"{cmd} up && {cmd} bclean")


@task
def fork_remote(c, username, remote="upstream"):
    """Configure a remote for a fork.

    https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/configuring-a-remote-for-a-fork
    """
    if username.startswith("-"):
        raise Exit("Arguments should be: [username] [--remote]")
    project = c.run(r"git remote -v | rg origin | head -1 | rg -o '/(.+)\.git' -r '$1'", pty=False).stdout.strip()
    c.run(f"git remote add {remote} https://github.com/{username}/{project}.git", warn=True)
    c.run("git remote -v")


@task
def fork_sync(c, remote="upstream"):
    """Sync a fork.

    https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/syncing-a-fork
    """
    c.run(f"git fetch {remote}")
    existing_branch = Git(c).checkout("master", "main")
    c.run(f"git merge {remote}/{existing_branch}")
    c.run("git push")


@task
def git_switch_url_to(c, remote="origin", https=False):
    """Set a SSH ot HTTPS URL for a remote."""
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


@task
def pre_commit_install(c, gc=False):
    """Pre-commit install scripts and hooks."""
    if gc:
        c.run("pre-commit gc")
    c.run("pre-commit install -t pre-commit -t commit-msg --install-hooks")


@task
def pre_commit_run(c, hook=""):
    """Pre-commit run all hooks or a specific one."""
    if hook:
        chosen_hook = run_with_fzf(c, "yq -r '.repos[].hooks[].id' .pre-commit-config.yaml", query=hook)
    else:
        chosen_hook = ""
    c.run(f"pre-commit run --all-files {chosen_hook}")


@task
def nitpick_auto(c):
    """Autoupdate nitpick hook with the latest tag."""
    c.run("pre-commit autoupdate --repo https://github.com/andreoliwa/nitpick")
    pre_commit_install(c, gc=True)


@task
def nitpick_bleed(c):
    """Autoupdate nitpick hook with the latest commit."""
    c.run("pre-commit autoupdate --bleeding-edge --repo https://github.com/andreoliwa/nitpick")
    pre_commit_install(c, gc=True)


@task
def jrnl_tags(c, sort=False, rg="", journal=""):
    """Query jrnl tags."""
    cmd = ["jrnl"]
    if journal:
        cmd.append(journal)
    cmd.append("--tags")
    if sort:
        cmd.append("| sort -u")
    if rg:
        cmd.append(f"| rg {rg}")
    c.run(" ".join(cmd))


@task
def jrnl_query(c, n=0, contains="", edit=False, fancy=False, short=False, journal=""):
    """Query jrnl entries."""
    format = "pretty"
    if fancy:
        format = "fancy"
    elif short:
        format = "short"

    cmd = ["jrnl"]
    if journal:
        cmd.append(journal)
    if n:
        cmd.append(f"-n {n}")
    cmd.append(f"--format {format}")
    if contains:
        cmd.append(f"-contains {contains}")
    if edit:
        cmd.append("--edit")
    c.run(" ".join(cmd))


@task
def jrnl_edit_last(c, journal=""):
    """Edit the last jrnl entry."""
    cmd = ["jrnl"]
    if journal:
        cmd.append(journal)
    cmd.append("-1 --edit")
    c.run(" ".join(cmd))


@task
def m3(c, browse=False):
    """Cleanup and backup pictures from the m3 hard.drive."""
    for line in c.run(f"fd -a -uu -t d \\.picasaorig {M3_PICTURES}", pty=False).stdout.splitlines():
        hidden_picasa_dir = Path(line)
        with c.cd(hidden_picasa_dir.parent):
            c.run("merge-dirs . .picasaoriginals/")

    year = 2000
    while year < date.today().year:
        year += 1
        dirs = c.run(f"fd -t d {year} {M3_PICTURES} | sort -u").stdout.splitlines()
        if not dirs:
            continue

        year_dir: Path = M3_PICTURES / str(year)
        year_dir.mkdir(exist_ok=True)

        for str_picture_dir in dirs:
            if not str_picture_dir:
                continue

            picture_dir = Path(str_picture_dir)
            if picture_dir == year_dir:
                # Skip the year dir itself
                continue

            c.run(f"du -sh {str_picture_dir!r}")
            if browse:
                c.run(f"open '{str_picture_dir}'")

            if picture_dir.parent != year_dir:
                # Skip dirs that were already moved
                c.run(f"mv {str_picture_dir!r} {str(year_dir)!r}")

    c.run("df -h")


@task
def onedrive(c, clean=True, number=1):
    """Open the latest N OneDrive photo dirs, to sort them out."""
    if clean:
        c.run("fd -uu -0 -tf -i .DS_Store ~/OneDrive | xargs -0 rm -v")
        c.run("find ~/OneDrive -mindepth 1 -type d -empty -print -delete")
    dirs = [f"~/OneDrive/Pictures/{sub}*" for sub in ["Telegram", "Whats_App_Documents", "Camera_New/20"]]
    run_command(
        c,
        "fd . -t f",
        *dirs,
        "| sort -r",
        f"| head -n {number}",
        "| xargs open -R",
    )


def ignore_module(module_name: str) -> bool:
    """Ignore a module by its name."""
    for ignore_str in CONJURING_IGNORE_MODULES:
        if ignore_str and ignore_str in module_name:
            return True
    return False


def add_tasks_directly(main_collection: Collection, module_path):
    """Add tasks directly to the collection, without prefix."""
    if isinstance(module_path, str):
        module = import_module(module_path)
        if ignore_module(module_path):
            return
    else:
        module = module_path
        if ignore_module(module.__name__):
            return
    sub_collection = Collection.from_module(module)
    for t in sub_collection.tasks.values():
        if t.name in main_collection.tasks:
            # Task already exists with the same name: add a suffix
            clean_name = module.__name__.strip("-_")
            main_collection.add_task(t, f"{t.name}-{clean_name}")
        else:
            main_collection.add_task(t)


def collection_from(*glob_patterns: str, prefix_root=False):
    """Create a custom collection by adding tasks from multiple files.

    Search directories for glob patterns:
    1. Root dir.
    2. Current dir.

    If the current dir is the root, tasks won't be duplicated.
    """
    # https://docs.python.org/3/library/os.html#os.stat_result
    current_inode = Path(__file__).stat().st_ino

    unique_patterns = set(glob_patterns)
    search_dirs: Set[Path] = {Path.cwd(), Path.home()}

    main_col = Collection()

    for which_dir in search_dirs:
        sys.path.insert(0, str(which_dir))
        for pattern in unique_patterns:
            for file in which_dir.glob(pattern):
                if file.stat().st_ino == current_inode:
                    # Don't add this file twice
                    continue
                add_tasks_directly(main_col, file.stem)
        sys.path.pop(0)

    if prefix_root:
        main_col.add_collection(Collection.from_module(sys.modules[__name__]), "root")
    else:
        add_tasks_directly(main_col, sys.modules[__name__])

    return main_col


namespace = collection_from("tasks.py", "*invoke*.py")
