"""Backup and restore with [Duplicity](https://duplicity.us/)."""

from pathlib import Path
from string import Template
from tempfile import NamedTemporaryFile

from invoke import Context, task
from my_den.utils import WOLT_DIR

from conjuring.constants import CODE_DIR
from conjuring.grimoire import print_success, print_warning, run_command, run_lines, run_with_fzf
from conjuring.spells.git import DOT_GIT, is_valid_git_repository

SHOULD_PREFIX = True
BACKUP_DIR = Path("~/OneDrive/Backup").expanduser()


def print_hostname(c: Context) -> str:
    """Print the hostname of the current machine."""
    host = c.run("hostname | sed 's/.local//'", dry=False).stdout.strip()
    print(f"Host: {host}")
    return host


@task
def backup(c: Context) -> None:
    """Backup files with Duplicity."""
    host = print_hostname(c)
    backup_dir = f"file://{BACKUP_DIR}/{host}/duplicity/"
    # To back up directly on OneDrive:
    # backup_dir = f"onedrive://Backup/{host}/duplicity/"
    print(f"Backup dir: {backup_dir}")

    print_success("Scanning repos:")
    files_to_append = []
    for line in run_lines(c, f"fd -u -t d --max-depth 2 {DOT_GIT}$ {CODE_DIR} {WOLT_DIR}"):
        repo = Path(line).parent
        if not is_valid_git_repository(repo):
            continue

        print_success(f"Files to keep in repo {repo}:")
        with c.cd(repo):
            for relative_path in run_lines(c, "git keep"):
                abs_path = (repo / relative_path).absolute()
                end_slash = "/" if abs_path.is_dir() else ""

                keep_file_path = f"{abs_path}{end_slash}"
                files_to_append.append(keep_file_path)

                print_func = print_warning if end_slash else print
                print_func(f"  {abs_path.relative_to(Path.home())}")

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
            f"--include-filelist={temp_file.name}",
            "--exclude='**' $HOME/",
            backup_dir,
        )


@task
def list_current_files(c: Context) -> None:
    """List all files included in the current duplicity backup."""
    host = print_hostname(c)
    backup_dir = f"file://{BACKUP_DIR}/{host}/duplicity/"
    print(f"Backup dir: {backup_dir}")

    c.run(f"duplicity list-current-files {backup_dir}")


@task
def restore(c: Context) -> None:
    """Restore files with Duplicity. You will be prompted to choose the source dir. Restore dir is ~/Downloads."""
    print_hostname(c)
    chosen_dir = run_with_fzf(c, f"fd -d 2 -t d duplicity {BACKUP_DIR}")
    if not chosen_dir:
        return

    source_computer = Path(chosen_dir).parent.name
    c.run(f"duplicity restore file://{chosen_dir} ~/Downloads/duplicity-restore/{source_computer}/")
