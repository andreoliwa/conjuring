"""Media files: remove empty dirs, clean up picture dirs, download YouTube videos, transcribe audio, ..."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from itertools import chain
from pathlib import Path

import typer
from invoke import Context, task

from conjuring.constants import (
    DESKTOP_DIR,
    DOT_DS_STORE,
    DOT_NOMEDIA,
    DOWNLOADS_DIR,
    ONEDRIVE_DIR,
    ONEDRIVE_PICTURES_DIR,
)
from conjuring.grimoire import print_warning, run_command, run_stdout

SHOULD_PREFIX = True

AUDIO_EXTENSIONS = {"mp3", "m4a", "wav", "aiff", "flac", "ogg", "wma"}


@task(
    help={
        "dir": "Directory to clean up. Default: current dir",
        "fd": "Use https://github.com/sharkdp/fd instead of 'find'",
        "force": "Delete the actual files (dotfiles are always deleted). Default: False",
    },
    iterable=["dir_"],
)
def rm_empty_dirs(c: Context, dir_: list[str | Path], force: bool = False, fd: bool = True) -> None:
    """Remove some hidden files first, then remove empty dirs.

    The ending slash is needed to search OneDrive, now that its behaviour changed in macOS Monterey.
    """
    if not dir_:
        dir_ = [Path.cwd()]

    dirs = list({str(Path(d).expanduser().absolute()) for d in dir_})
    xargs = "xargs -0 -n 1 rm -v"
    for hidden_file in [DOT_DS_STORE, DOT_NOMEDIA]:
        if fd:
            c.run(f"fd -uu -0 -tf -i {hidden_file} {'/ '.join(dirs)}/ | {xargs}")
        else:
            for one_dir in dirs:
                c.run(f"find {one_dir}/ -type f -iname {hidden_file} -print0 | {xargs}")

    f_option = " ".join([f"-f {d}/" for d in dirs[:-1]])
    delete_flag = "-delete" if force else ""
    run_command(c, "find", f_option, f"{dirs[-1]}/ -mindepth 1 -type d -empty -print", delete_flag)
    if not force:
        print_warning("[DRY RUN] Run with --force to actually delete the files")


@task
def cleanup(c: Context, browse: bool = False) -> None:
    """Cleanup pictures."""
    c.run(f"fd -H -0 -tf -i {DOT_DS_STORE} | xargs -0 rm -v")
    c.run(f"fd -H -0 -tf -i {DOT_NOMEDIA} | xargs -0 rm -v")
    c.run("find . -mindepth 1 -type d -empty -print -delete")

    # Unhide Picasa originals dir
    for line in c.run("fd -H -t d .picasaoriginals", pty=False).stdout.splitlines():
        original_dir = Path(line)
        c.run(f"mv {original_dir} {original_dir.parent}/Picasa_Originals")

    # Keep the original dir as the main dir and rename parent dir to "_Copy"
    for line in c.run("fd -t d originals", pty=False).stdout.splitlines():
        original_dir = Path(line)
        c.run(f"mv {original_dir} {original_dir.parent}_Temp")
        c.run(f"mv {original_dir.parent} {original_dir.parent}_Copy")
        c.run(f"mv {original_dir.parent}_Temp {original_dir.parent}")

    # Merge the copy dir with the main one
    for line in run_command(c, "fd -a -uu -t d --color never _copy", str(ONEDRIVE_PICTURES_DIR)).stdout.splitlines():
        copy_dir = Path(line)
        original_dir = Path(line.replace("_Copy", ""))
        if original_dir.exists():
            if browse:
                c.run(f"open '{original_dir}'")
            c.run(f"merge-dirs '{original_dir}' '{copy_dir}'")
        else:
            c.run(f"mv '{copy_dir}' '{original_dir}'")

    # List dirs with _Copy files
    copy_dirs = set()
    for line in run_command(
        c,
        "fd -H -t f --color never _copy",
        str(ONEDRIVE_PICTURES_DIR),
        hide=True,
    ).stdout.splitlines():
        copy_dirs.add(Path(line).parent)

    for dir_ in sorted(copy_dirs):
        typer.echo(dir_)


@task(
    help={
        "organize": "Call 'organize run' before categorizing",
        "browse": "Open dir on Finder",
        "empty": "Check dirs that are not empty but should be",
    },
)
def categorize(c: Context, organize: bool = True, browse: bool = True, empty: bool = True) -> None:
    """Open directories with files/photos that have to be categorized/moved/renamed."""
    if organize:
        c.run("invoke organize")

    empty_dirs = (
        [
            Path(str(d)).expanduser()
            for d in [
                DOWNLOADS_DIR,
                DESKTOP_DIR,
                "~/Documents/Shared_Downloads",
                ONEDRIVE_PICTURES_DIR / "Telegram",
                ONEDRIVE_PICTURES_DIR / "Samsung_Gallery/Pictures/Telegram",
                ONEDRIVE_DIR / "Documents/Mayan_Staging/Portugues",
                ONEDRIVE_DIR / "Documents/Mayan_Staging/English",
                ONEDRIVE_DIR / "Documents/Mayan_Staging/Deutsch",
            ]
        ]
        if empty
        else []
    )

    current_year = datetime.now(tz=timezone.utc).date().year
    picture_dirs = [
        Path(ONEDRIVE_PICTURES_DIR) / f"Camera_New/{sub}" for sub in chain([current_year], range(2008, current_year))
    ]

    for path in chain(empty_dirs, picture_dirs):  # type: Path
        if not path.exists():
            continue
        has_files = False
        for file in path.glob("*"):
            if not file.name.startswith("."):
                has_files = True
                break
        if not has_files:
            continue

        if browse:
            last_file = run_stdout(
                c,
                "fd . -t f --color never",
                str(path),
                "| sort -ru",
                "| head -1",
            )
            run_command(c, f"open -R {last_file!r}")
            break

        typer.echo(str(path))


@task
def youtube_dl(c: Context, url: str, min_height: int = 240, download_archive_path: str = "") -> None:
    """Download video URLs, try different low-res formats until it finds one."""
    download_archive_path = download_archive_path or os.environ.get("YOUTUBE_DL_DOWNLOAD_ARCHIVE_PATH", "")
    archive_option = f"--download-archive {download_archive_path!r}" if download_archive_path else ""

    all_heights = [h for h in [240, 360, 480, 0] if h >= min_height or h == 0]
    for height in all_heights:
        # https://github.com/ytdl-org/youtube-dl#format-selection-examples
        # Download best format available but no better than the chosen height
        fmt = f"-f 'bestvideo[height<={height}]+bestaudio/best[height<={height}]'" if height else ""

        result = run_command(
            c,
            "youtube-dl --ignore-errors --restrict-filenames",
            # "--get-title --get-id",
            # "--get-thumbnail --get-description --get-duration --get-filename",
            # "--get-format",
            archive_option,
            fmt,
            url,
            warn=True,
        )
        if result.ok or "Unsupported URL:" in result.stdout:
            break


@task
def slideshow(c: Context, start_at: str = "") -> None:
    """Show pictures in the current dir with feh."""
    start_at_option = f"--start-at {start_at}" if start_at else ""
    run_command(c, "feh -r -. -g 1790x1070 -B black --caption-path .", start_at_option)


@task(help={"dir_": "Directory with audios to transcribe"})
def whisper(c: Context, dir_: str | Path) -> None:
    """Transcribe multiple audio file that haven't been transcribed yet, using whisper."""
    dir_ = Path(dir_).expanduser()
    audios: list[Path] = []
    for extension in AUDIO_EXTENSIONS:
        audios.extend(dir_.glob(f"*.{extension}"))
    for file in audios:
        transcript_file = file.with_suffix(".txt")
        if not transcript_file.exists():
            c.run(f"whisper --language pt -f txt '{file}' --output_dir '{file.parent}'")
            continue
        c.run(f"open '{transcript_file}'")
