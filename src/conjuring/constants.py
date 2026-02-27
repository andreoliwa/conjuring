"""Paths, filenames and other constants."""

from __future__ import annotations

import re
from pathlib import Path

# keep-sorted start
AWS_CONFIG = Path("~/.aws/config").expanduser()
CODE_DIR = Path("~/Code").expanduser()
CONJURING_INIT = "conjuring_init"
CONJURING_SPELLS_DIR = Path(__file__).parent / "spells"
DESKTOP_DIR = Path("~/Desktop").expanduser()
DEV_DIR = Path.home() / "dev"
DEV_ME_DIR = DEV_DIR / "me"
DOCUMENTS_DIR = Path("~/Documents").expanduser()
DOT_DS_STORE = ".DS_Store"
DOT_NOMEDIA = ".nomedia"
DOWNLOADS_DIR = Path("~/Downloads").expanduser()
ONEDRIVE_DIR = Path("~/OneDrive").expanduser()
ONEDRIVE_PICTURES_DIR = ONEDRIVE_DIR / "Pictures"
PICTURES_DIR = Path("~/Pictures").expanduser()
PRE_COMMIT_CONFIG_YAML = ".pre-commit-config.yaml"
PYPROJECT_TOML = "pyproject.toml"
REGEX_JIRA_TICKET_TITLE = re.compile(r"^(?P<ticket>[A-Z]+-\d+)\s*(?P<title>.+)?")
ROOT_INVOKE_YAML = Path("~/.invoke.yaml").expanduser()
STOP_FILE_OR_DIR = Path.home() / "stop"
# keep-sorted end
