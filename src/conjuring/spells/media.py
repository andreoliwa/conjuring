import os
from datetime import date
from itertools import chain
from pathlib import Path

from invoke import task

from conjuring.grimoire import run_command

SHOULD_PREFIX = True
ONE_DRIVE_DIR = Path("~/OneDrive").expanduser()
PICTURES_DIR = ONE_DRIVE_DIR / "Pictures"


@task
def cleanup(c, browse=False):
    """Cleanup pictures."""
    c.run("fd -H -0 -tf -i .DS_Store | xargs -0 rm -v")
    c.run("fd -H -0 -tf -i .nomedia | xargs -0 rm -v")
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
    for line in run_command(c, "fd -a -uu -t d --color never _copy", str(PICTURES_DIR)).stdout.splitlines():
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
    for line in run_command(c, "fd -H -t f --color never _copy", str(PICTURES_DIR), hide=True).stdout.splitlines():
        copy_dirs.add(Path(line).parent)

    for dir_ in sorted(copy_dirs):
        print(dir_)


@task(
    help={
        "organize": "Call 'organize run' before categorizing",
        "browse": "Open dir on Finder",
        "empty": "Check dirs that are not empty but should be",
    }
)
def categorize(c, organize=True, browse=True, empty=True):
    """Open directories with files/photos that have to be categorized/moved/renamed."""
    if organize:
        c.run("organize run")

    empty_dirs = (
        [
            Path(d).expanduser()
            for d in [
                "~/Downloads",
                "~/Desktop",
                "~/Documents/Shared_Downloads",
                PICTURES_DIR / "Telegram",
                PICTURES_DIR / "Samsung_Gallery/Pictures/Telegram",
                ONE_DRIVE_DIR / "Documents/Mayan_Staging/Portugues",
                ONE_DRIVE_DIR / "Documents/Mayan_Staging/English",
                ONE_DRIVE_DIR / "Documents/Mayan_Staging/Deutsch",
            ]
        ]
        if empty
        else []
    )

    current_year = date.today().year
    picture_dirs = [
        Path(PICTURES_DIR) / f"Camera_New/{sub}" for sub in chain([current_year], range(2008, current_year))
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
            run_command(
                c,
                "fd . -0 -t f --color never -1",
                str(path),
                "| xargs -0 open -R",
            )
            break
        else:
            print(str(path))


@task
def youtube_dl(c, url, min_height=240, download_archive_path=""):
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
