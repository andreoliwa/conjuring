"""Media files: remove empty dirs, clean up picture dirs, download YouTube videos, transcribe audio."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from itertools import chain
from pathlib import Path

import typer
from humanize import naturalsize
from invoke import Context, task
from tqdm import tqdm

from conjuring.constants import (
    DESKTOP_DIR,
    DOT_DS_STORE,
    DOT_NOMEDIA,
    DOWNLOADS_DIR,
    ONEDRIVE_DIR,
    ONEDRIVE_PICTURES_DIR,
    STOP_FILE_OR_DIR,
)
from conjuring.grimoire import (
    check_stop_file,
    iter_path_with_progress,
    print_error,
    print_normal,
    print_success,
    print_warning,
    run_command,
    run_lines,
    run_stdout,
    unique_file_name,
)

SHOULD_PREFIX = True

AUDIO_EXTENSIONS = {"mp3", "m4a", "wav", "aiff", "flac", "ogg", "wma"}
MAX_COUNT = 1000
MAX_SIZE = 1_000_000_000  # 1 GB


@task(
    help={
        "dir": "Directory to clean up. Default: current dir",
        "fd": "Use https://github.com/sharkdp/fd instead of 'find'",
        "delete": "Delete the actual files (dotfiles are always deleted). Default: False",
    },
    iterable=["dir_"],
)
def empty_dirs(c: Context, dir_: list[str | Path], delete: bool = False, fd: bool = True) -> None:
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
    delete_flag = "-delete" if delete else ""
    run_command(c, "find", f_option, f"{dirs[-1]}/ -mindepth 1 -type d -empty -print", delete_flag)
    if not delete:
        print_warning("Run with --delete to actually delete the files", dry=True)


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
        "browse": "How many dirs to open on on Finder",
        "empty": "Check dirs that are not empty but should be",
    },
)
def categorize(c: Context, organize: bool = True, browse: int = 3, empty: bool = True) -> None:
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

    count = 0
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
            if last_file:
                run_command(c, f"open -R {last_file!r}")
                count += 1
                if count >= browse:
                    break

        typer.echo(str(path))


@task
def youtube_dl(c: Context, url: str, min_height: int = 360, download_archive_path: str = "") -> None:
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


class CompareDirsAction(Enum):
    """Actions to take when comparing two directories."""

    # keep-sorted start
    DELETE_IDENTICAL = "identical_deleted"
    DIFF_FAILED = "diff_failed"
    DO_NOTHING = None
    MOVE_IDENTICAL = "identical"
    MOVE_NOT_FOUND = "not_found"
    # keep-sorted end


@task(
    help={
        "from_dir": "Source root directory to compare from",
        "to_dir": "Destination root directory to compare to",
        "count": f"Max number of files to compare. Default: {MAX_COUNT}",
        "size": f"Max size of files to compare. Default: {naturalsize(MAX_SIZE)}",
        "delete": "Delete identical files from the source dir",
        "move": "Move identical files from the source dir to the output dir",
        "wildcard_search": "If not found with the exact name,"
        " search the destination dir using the file name with wildcards",
    },
)
def compare_dirs(  # noqa: PLR0913
    c: Context,
    from_dir: str,
    to_dir: str,
    count: int = MAX_COUNT,
    size: int = MAX_SIZE,
    delete: bool = False,
    move: bool = False,
    wildcard_search: bool = False,
) -> None:
    """Compare files in two directories. Stops when it reaches max count or size."""
    if delete and move:
        print_error("Choose either --delete or --move, not both")
        return
    dry = not (delete or move) or c.config.run.dry

    # Use a slug to compare multiple dirs at the same time
    abs_from_dir = Path(from_dir).expanduser().absolute()
    slug = str(abs_from_dir.relative_to(Path.home())).replace(os.sep, "-")
    output_dir = DOWNLOADS_DIR / "compare-dirs-output" / slug

    print_success("Output dir:", str(output_dir), "/ Stop file or dir:", str(STOP_FILE_OR_DIR))

    current_count = 0
    current_size = 0

    max_results = f"--max-results {count}" if count else ""
    lines = run_lines(c, "fd -t f -u", max_results, ".", str(abs_from_dir), "| sort", dry=False)

    with tqdm(lines) as pbar:
        for line in pbar:
            if check_stop_file():
                break

            source_file: Path = Path(line).absolute()
            if source_file.name == DOT_DS_STORE:
                continue

            current_count += 1
            file_size = source_file.stat().st_size
            current_size += file_size

            partial_source_path = source_file.relative_to(abs_from_dir)
            destination_file: Path = to_dir / partial_source_path

            action, file_description = _determine_action(
                c,
                source_file,
                to_dir,
                destination_file,
                delete,
                move,
                wildcard_search,
            )

            pbar.set_postfix(count=current_count, size=naturalsize(file_size), total_size=naturalsize(current_size))

            # Check the file size after running the diff, so remote on-demand files are downloaded locally
            if size and current_size > size:
                print_error(
                    f"Current size ({naturalsize(current_size)})",
                    f"exceeded --size ({naturalsize(size)}), stopping",
                    dry=dry,
                )
                break

            if action == CompareDirsAction.DO_NOTHING:
                print_normal(file_description, dry=dry)
                continue

            _execute(
                action,
                source_file,
                file_description,
                output=output_dir / action.value / partial_source_path,
                dry=dry,
            )


def _determine_action(  # noqa: PLR0913
    c: Context,
    source_file: Path,
    to_dir: str,
    destination_file: Path,
    delete: bool,
    move: bool,
    wildcard_search: bool,
) -> tuple[CompareDirsAction, str]:
    action = CompareDirsAction.DO_NOTHING
    if not destination_file.exists():
        if wildcard_search:
            # Clean common chars to try to find a file that was renamed in a simple way
            clean_stem = source_file.stem
            for char in "_-() ":
                clean_stem = clean_stem.replace(char, "?")
            quoted_regex_name = f'".*{clean_stem}.*{source_file.suffix}"'
            found_lines = run_lines(c, f"fd -t f -u {quoted_regex_name}", str(to_dir), dry=False, hide=False)
            if found_lines:
                if len(found_lines) > 1:
                    return action, f"Found more than one file for {quoted_regex_name}: {found_lines}"

                destination_file = Path(found_lines[0]).absolute()
                return _compare_files(c, source_file, destination_file, delete, move)

        if delete or move:
            action = CompareDirsAction.MOVE_NOT_FOUND
        return action, f"Missing file {destination_file}"

    return _compare_files(c, source_file, destination_file, delete, move)


def _compare_files(
    c: Context,
    source_file: Path,
    destination_file: Path,
    delete: bool,
    move: bool,
) -> tuple[CompareDirsAction, str]:
    action = CompareDirsAction.DO_NOTHING
    result = c.run(f'diff "{source_file}" "{destination_file}"', dry=c.config.run.dry, warn=True)
    if c.config.run.dry:
        file_description = "diff command was not actually executed"
    elif result.ok:
        file_description = "Identical file"
        if delete:
            action = CompareDirsAction.DELETE_IDENTICAL
        elif move:
            action = CompareDirsAction.MOVE_IDENTICAL
    else:
        file_description = "File with failed diff"
        if delete or move:
            action = CompareDirsAction.DIFF_FAILED
    return action, file_description


def _execute(action: CompareDirsAction, source_file: Path, file_description: str, *, output: Path, dry: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if action == CompareDirsAction.DELETE_IDENTICAL:
        if not dry:
            source_file.unlink()
            output.touch()
        print_warning(f"{file_description} deleted from {source_file}", dry=dry)
    elif action in (
        CompareDirsAction.MOVE_IDENTICAL,
        CompareDirsAction.MOVE_NOT_FOUND,
        CompareDirsAction.DIFF_FAILED,
    ):
        if not dry:
            source_file.rename(output)
        print_success(f"{file_description} moved to {output}", dry=dry)
    else:
        msg = f"Unexpected {action}, adjust the code"
        raise RuntimeError(msg)


@task(
    help={
        "dir": "Root directory to zip. Default: current dir",
        "count": "Max number of sub dirs to zip. Default: 1",
        "delete": "Delete the directory after zipping with success. Default: False",
    },
    iterable=["dir_"],
)
def zip_tree(c: Context, dir_: list[str | Path], count: int = 1, depth: int = 5, delete: bool = False) -> None:
    """Zip files in a directory tree, creating a .tar.gz file."""
    if not dir_:
        dir_ = [Path.cwd()]

    for raw_dir in dir_:
        path_dir = Path(raw_dir)
        for path_to_zip in iter_path_with_progress(
            c,
            "-t f --exclude '*.tar.gz' .",
            str(raw_dir),
            "--exec echo {//} | sort --unique --ignore-case",
            max_count=count,
            reverse_depth=depth,
        ):
            if path_to_zip == path_dir:
                continue

            tar_gz_file = unique_file_name(path_to_zip.with_suffix(".tar.gz"))
            with c.cd(path_to_zip.parent):
                run_command(
                    c,
                    "gtar",
                    "--remove-files" if delete else "",
                    "--exclude='*.tar.gz'",
                    f'-czf "{tar_gz_file.name}" -C . "./{path_to_zip.name}"',
                    warn=True,
                )


@task(
    help={
        "dir": "Root directory to unzip. Default: current dir",
        "count": "Max number of files to unzip. Default: 1",
        "delete": "Delete the .tar.gz file after unzipping with success. Default: False",
    },
    iterable=["dir_"],
)
def unzip_tree(c: Context, dir_: list[str | Path], count: int = 1, delete: bool = False) -> None:
    """Unzip .tar.gz files in a directory tree."""
    if not dir_:
        dir_ = [Path.cwd()]

    for one_dir in dir_:
        for tar_gz_path in iter_path_with_progress(
            c,
            "-t f .tar.gz",
            str(one_dir),
            "| sort --ignore-case",
            max_count=count,
        ):
            result = run_command(c, f"gtar -xzf '{tar_gz_path}' -C '{tar_gz_path.parent}'")
            if result.ok and delete:
                run_command(c, f"rm '{tar_gz_path}'")
