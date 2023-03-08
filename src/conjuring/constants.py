from pathlib import Path

DESKTOP_DIR = Path("~/Desktop").expanduser()
DOCUMENTS_DIR = Path("~/Documents").expanduser()
DOWNLOADS_DIR = Path("~/Downloads").expanduser()
ONE_DRIVE_DIR = Path("~/OneDrive").expanduser()
PICTURES_DIR = ONE_DRIVE_DIR / "Pictures"

DOT_DS_STORE = ".DS_Store"
DOT_NO_MEDIA = ".nomedia"
