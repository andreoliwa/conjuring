"""Backup and restore with [Duplicity](https://duplicity.us/)."""

from pathlib import Path
from string import Template
from tempfile import NamedTemporaryFile

import typer
from invoke import Context, task

from conjuring.grimoire import run_command, run_with_fzf

SHOULD_PREFIX = True
BACKUP_DIR = Path("~/OneDrive/Backup").expanduser()


def print_hostname(c: Context) -> str:
    """Print the hostname of the current machine."""
    host = c.run("hostname | sed 's/.local//'", dry=False).stdout.strip()
    typer.echo(f"Host: {host}")
    return host


@task
def backup(c: Context) -> None:
    """Backup files with Duplicity."""
    host = print_hostname(c)
    backup_dir = f"file://{BACKUP_DIR}/{host}/duplicity/"
    # To back up directly on OneDrive:
    # backup_dir = f"onedrive://Backup/{host}/duplicity/"
    typer.echo(f"Backup dir: {backup_dir}")

    template_file = Path("~/dotfiles/backup-duplicity-template.cfg").expanduser()
    typer.echo(f"Template file: {template_file}")

    template_contents = template_file.read_text()
    duplicity_config = Template(template_contents).substitute({"HOME": Path.home()})

    with NamedTemporaryFile("r+", delete=False) as temp_file:
        temp_file.write(duplicity_config)
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
def restore(c: Context) -> None:
    """Restore files with Duplicity. You will be prompted to choose the source dir. Restore dir is ~/Downloads."""
    print_hostname(c)
    chosen_dir = run_with_fzf(c, f"fd -d 2 -t d duplicity {BACKUP_DIR}")
    if not chosen_dir:
        return

    source_computer = Path(chosen_dir).parent.name
    c.run(f"duplicity restore file://{chosen_dir} ~/Downloads/duplicity-restore/{source_computer}/")
