"""Backup and restore with [Duplicity](https://duplicity.us/)."""

from pathlib import Path
from string import Template
from tempfile import NamedTemporaryFile

from invoke import Context, task

from conjuring.colors import Color
from conjuring.grimoire import (
    get_hostname,
    lazy_env_variable,
    print_color,
    print_success,
    run_command,
    run_lines,
    run_with_fzf,
)
from conjuring.spells.git import DOT_GIT, is_valid_git_repository

SHOULD_PREFIX = True


def _backup_dest_dir(host: str) -> str:
    dest = lazy_env_variable(
        "DUPLICITY_DEST_DIR", "base directory for duplicity backups (e.g. /Users/you/OneDrive/Backup)"
    )
    return f"file://{dest}/{host}/duplicity/"


def _backup_source_dirs() -> list[Path]:
    raw = lazy_env_variable(
        "DUPLICITY_BACKUP_DIRS", "colon-separated list of root directories to scan for git repos (e.g. ~/dev:~/Code)"
    )
    return [Path(p).expanduser() for p in raw.split(":") if p]


def print_hostname(c: Context) -> str:
    """Print and return the short hostname of the current machine."""
    host = get_hostname()
    print(f"Host: {host}")
    return host


def _planned_files(c: Context, repo_root: list[str], display: bool = False) -> list[str]:
    """Return the list of absolute paths that would be included in the next backup."""
    files_to_append = []
    source_dirs = " ".join(str(d) for d in _backup_source_dirs())
    joined_repo_roots = " ".join([str(one_root) for one_root in repo_root])
    for line in run_lines(c, f"fd -u -t d --max-depth 2 {DOT_GIT}$ {source_dirs} {joined_repo_roots}"):
        repo = Path(line).parent
        if not is_valid_git_repository(repo):
            continue

        with c.cd(repo):
            for relative_path in run_lines(c, "git keep"):
                abs_path = (repo / relative_path).absolute()

                # No trailing slash: duplicity recurses into dirs only without it
                files_to_append.append(str(abs_path))

                if display:
                    if abs_path.is_dir():
                        print_color(Color.BOLD_BLUE, str(abs_path) + "/")
                    else:
                        print(str(abs_path))

    return files_to_append


@task(
    help={
        "repo_root": "Optional root directory of the repositories to backup. Can be used multiple times.",
        "allow_source_mismatch": "Pass --allow-source-mismatch to duplicity (use once after hostname change).",
    },
    iterable=["repo_root"],
)
def backup(c: Context, repo_root: list[str], allow_source_mismatch: bool = False) -> None:
    """Backup files with Duplicity."""
    host = print_hostname(c)
    backup_dir = _backup_dest_dir(host)
    print(f"Backup dir: {backup_dir}")

    files_to_append = _planned_files(c, repo_root)

    template_file = Path("~/dotfiles/backup-duplicity-template.cfg").expanduser()
    print(f"Template file: {template_file}")

    template_contents = template_file.read_text()
    duplicity_config = Template(template_contents).substitute({"HOME": Path.home()})

    with NamedTemporaryFile("r+", delete=False) as temp_file:
        temp_file.write(duplicity_config)
        temp_file.write("\n".join(files_to_append))
        temp_file.flush()
        run_command(
            c,
            "duplicity",
            f"--name='{host}-backup'",
            "-v info",
            "--dry-run" if c.config.run.dry else "",
            "--allow-source-mismatch" if allow_source_mismatch else "",
            f"--include-filelist={temp_file.name}",
            "--exclude='**' $HOME/",
            backup_dir,
            dry=False,
        )


@task(
    help={
        "archived": "List files in the existing backup archive (last run).",
        "planned": "List files that would be included in the next backup.",
        "repo_root": "Optional root directory of the repositories to scan for planned files. Repeatable.",
        "host": "Hostname whose backup to inspect (default: current machine).",
    },
    iterable=["repo_root"],
)
def ls(c: Context, archived: bool = False, planned: bool = False, repo_root: list[str] = [], host: str = "") -> None:  # noqa: B006
    """List files included in the duplicity backup (archived = last run, planned = next run).

    If neither flag is set, both sections are shown.
    """
    show_all = not archived and not planned
    if host:
        print(f"Host: {host}")
    else:
        host = print_hostname(c)
    backup_dir = _backup_dest_dir(host)
    print(f"Backup dir: {backup_dir}")

    if archived or show_all:
        print_success("Archived files (last backup):")
        c.run(f"duplicity list-current-files {backup_dir}")

    if planned or show_all:
        print_success("Planned files (next backup):")
        _planned_files(c, repo_root, display=True)


@task
def restore(c: Context) -> None:
    """Restore files with Duplicity. You will be prompted to choose the source dir. Restore dir is ~/Downloads."""
    print_hostname(c)
    dest = lazy_env_variable("DUPLICITY_DEST_DIR", "base directory for duplicity backups")
    chosen_dir = run_with_fzf(c, f"fd -d 2 -t d duplicity {dest}")
    if not chosen_dir:
        return

    source_computer = Path(chosen_dir).parent.name
    c.run(f"duplicity restore file://{chosen_dir} ~/Downloads/duplicity-restore/{source_computer}/")
