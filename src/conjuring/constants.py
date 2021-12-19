import os
from pathlib import Path

COLOR_NONE = "\033[0m"
COLOR_CYAN = "\033[36m"
COLOR_LIGHT_GREEN = "\033[1;32m"
COLOR_LIGHT_RED = "\033[1;31m"

CONJURING_IGNORE_MODULES = os.environ.get("CONJURING_IGNORE_MODULES", "").split(",")
ONE_DRIVE_DIR = Path("~/OneDrive").expanduser()
BACKUP_DIR = ONE_DRIVE_DIR / "Backup"
PICTURES_DIR = ONE_DRIVE_DIR / "Pictures"
