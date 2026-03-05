from pathlib import Path
from unittest.mock import patch

import pytest
from invoke import Context


def test_claude_patch_exits_when_no_files_found(tmp_path: Path) -> None:
    """Exits non-zero when no hookify config_loader.py is found."""
    from conjuring.spells.ai import claude_patch

    with patch.object(Path, "glob", return_value=[]), patch.object(Path, "exists", return_value=False):
        with pytest.raises(SystemExit) as exc:
            claude_patch(Context())
        assert exc.value.code == 1


def test_claude_patch_patches_file(tmp_path: Path) -> None:
    """Replaces OLD_STRING with NEW_STRING in a target file."""
    from conjuring.spells.ai import NEW_STRING, OLD_STRING, claude_patch

    target = tmp_path / "config_loader.py"
    target.write_text(f"import os\nimport glob\n{OLD_STRING}")

    with patch.object(Path, "glob", return_value=[target]), patch.object(Path, "exists", return_value=False):
        claude_patch(Context())

    result = target.read_text()
    assert OLD_STRING not in result
    assert NEW_STRING in result


def test_claude_patch_is_idempotent(tmp_path: Path) -> None:
    """Skips files that are already patched (no OLD_STRING present)."""
    from conjuring.spells.ai import NEW_STRING, claude_patch

    target = tmp_path / "config_loader.py"
    original_content = f"import os\nimport glob\n{NEW_STRING}"
    target.write_text(original_content)

    with patch.object(Path, "glob", return_value=[target]), patch.object(Path, "exists", return_value=False):
        claude_patch(Context())

    assert target.read_text() == original_content


def test_claude_patch_patches_multiple_files(tmp_path: Path) -> None:
    """Patches all matched files (marketplace + multiple cache versions)."""
    from conjuring.spells.ai import NEW_STRING, OLD_STRING, claude_patch

    file1 = tmp_path / "v1" / "config_loader.py"
    file2 = tmp_path / "v2" / "config_loader.py"
    file1.parent.mkdir()
    file2.parent.mkdir()
    file1.write_text(OLD_STRING)
    file2.write_text(OLD_STRING)

    with patch.object(Path, "glob", return_value=[file1, file2]), patch.object(Path, "exists", return_value=False):
        claude_patch(Context())

    assert NEW_STRING in file1.read_text()
    assert NEW_STRING in file2.read_text()
