"""Paths, filenames and other constants."""

import re
from pathlib import Path

# Paths
# keep-sorted start
CODE_DIR = Path("~/Code").expanduser()
CONJURING_SPELLS_DIR = Path(__file__).parent / "spells"
DESKTOP_DIR = Path("~/Desktop").expanduser()
DOCUMENTS_DIR = Path("~/Documents").expanduser()
DOWNLOADS_DIR = Path("~/Downloads").expanduser()
ONEDRIVE_DIR = Path("~/OneDrive").expanduser()
PICTURES_DIR = Path("~/Pictures").expanduser()
# keep-sorted end
ONEDRIVE_PICTURES_DIR = ONEDRIVE_DIR / "Pictures"

# Filenames
# keep-sorted start
AWS_CONFIG = Path("~/.aws/config").expanduser()
CONJURING_INIT = "conjuring_init"
DOT_DS_STORE = ".DS_Store"
DOT_NOMEDIA = ".nomedia"
PRE_COMMIT_CONFIG_YAML = ".pre-commit-config.yaml"
PYPROJECT_TOML = "pyproject.toml"
ROOT_INVOKE_YAML = Path("~/.invoke.yaml").expanduser()
STOP_FILE_OR_DIR = Path.home() / "stop"
# keep-sorted end
REGEX_JIRA_TICKET_TITLE = re.compile(r"^(?P<ticket>[A-Z]+-\d+)\s*(?P<title>.+)?")
