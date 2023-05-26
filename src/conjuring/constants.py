"""Paths, filenames and other constants."""
from pathlib import Path

# Paths
CONJURING_SPELLS_DIR = Path(__file__).parent / "spells"
DESKTOP_DIR = Path("~/Desktop").expanduser()
DOCUMENTS_DIR = Path("~/Documents").expanduser()
DOWNLOADS_DIR = Path("~/Downloads").expanduser()
ONEDRIVE_DIR = Path("~/OneDrive").expanduser()
ONEDRIVE_PICTURES_DIR = ONEDRIVE_DIR / "Pictures"

# Filenames
AWS_CONFIG = Path("~/.aws/config").expanduser()
CONJURING_INIT = "conjuring_init"
DOT_DS_STORE = ".DS_Store"
DOT_NOMEDIA = ".nomedia"
PRE_COMMIT_CONFIG_YAML = ".pre-commit-config.yaml"
PYPROJECT_TOML = "pyproject.toml"
ROOT_INVOKE_YAML = Path("~/.invoke.yaml").expanduser()
