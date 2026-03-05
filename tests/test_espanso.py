import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from invoke import Collection

from conjuring.grimoire import magically_add_tasks


def test_espanso_module_has_prefix() -> None:
    """Test that espanso module uses SHOULD_PREFIX."""
    from conjuring.spells import espanso

    assert hasattr(espanso, "SHOULD_PREFIX")
    assert espanso.SHOULD_PREFIX is True


def test_espanso_import_task_exists() -> None:
    """Test that import task is discoverable."""
    from conjuring.spells import espanso

    collection = Collection("test")
    magically_add_tasks(collection, espanso)

    assert "espanso.import" in collection.task_names or "espanso.import-replacements" in collection.task_names


def test_extract_macos_replacements_success() -> None:
    """Test successful extraction of macOS replacements."""
    from conjuring.spells.espanso import extract_macos_replacements

    mock_plist = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<array>
    <dict>
        <key>on</key>
        <string>1</string>
        <key>replace</key>
        <string>iirc</string>
        <key>with</key>
        <string>if I recall correctly</string>
    </dict>
    <dict>
        <key>on</key>
        <string>0</string>
        <key>replace</key>
        <string>disabled</string>
        <key>with</key>
        <string>ShouldNotAppear</string>
    </dict>
    <dict>
        <key>on</key>
        <string>1</string>
        <key>replace</key>
        <string>smp</string>
        <key>with</key>
        <string>Show me your plan</string>
    </dict>
</array>
</plist>"""

    raw_mock = Mock(returncode=0, stdout=b"raw plist data")
    converted_mock = Mock(returncode=0, stdout=mock_plist)

    with patch("subprocess.run", side_effect=[raw_mock, converted_mock]):
        result = extract_macos_replacements()

    assert len(result) == 2
    assert ("iirc", "if I recall correctly") in result
    assert ("smp", "Show me your plan") in result
    assert ("disabled", "ShouldNotAppear") not in result


def test_extract_macos_replacements_command_fails() -> None:
    """Test handling when defaults command fails."""
    from conjuring.spells.espanso import extract_macos_replacements

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=1, stdout=b"", stderr=b"error")
        result = extract_macos_replacements()

    assert result == []


def test_scan_existing_espanso_configs() -> None:
    """Test scanning existing espanso YAML files."""
    from conjuring.spells.espanso import scan_existing_espanso_configs

    with tempfile.TemporaryDirectory() as tmpdir:
        match_dir = Path(tmpdir) / "match"
        match_dir.mkdir()

        (match_dir / "base.yml").write_text(
            'matches:\n  - trigger: "brb"\n    replace: "be right back"\n'
            '  - trigger: "tbh"\n    replace: "to be honest"\n',
        )
        (match_dir / "custom.yml").write_text('matches:\n  - trigger: "smp"\n    replace: "Show me your plan"\n')

        result = scan_existing_espanso_configs(match_dir)

    assert len(result) == 3
    assert ("brb", "be right back") in result
    assert ("tbh", "to be honest") in result
    assert ("smp", "Show me your plan") in result


def test_scan_espanso_configs_handles_missing_matches_key() -> None:
    """Test handling YAML files without matches key."""
    from conjuring.spells.espanso import scan_existing_espanso_configs

    with tempfile.TemporaryDirectory() as tmpdir:
        match_dir = Path(tmpdir) / "match"
        match_dir.mkdir()
        (match_dir / "empty.yml").write_text("# Just a comment\n")
        (match_dir / "other.yml").write_text("somekey: value\n")

        result = scan_existing_espanso_configs(match_dir)

    assert result == set()


def test_scan_espanso_configs_nonexistent_dir() -> None:
    """Test handling nonexistent directory."""
    from conjuring.spells.espanso import scan_existing_espanso_configs

    result = scan_existing_espanso_configs(Path("/nonexistent/path"))
    assert result == set()


def test_filter_duplicates() -> None:
    """Test filtering out exact duplicate matches."""
    from conjuring.spells.espanso import filter_duplicates

    macos_replacements = [
        ("afk", "away from keyboard"),
        ("smp", "Show me your plan"),
        ("new", "NewReplacement"),
    ]
    existing_matches = {
        ("afk", "away from keyboard"),  # exact match - filtered
        ("smp", "Different text"),  # same trigger, different text - kept
    }

    result = filter_duplicates(macos_replacements, existing_matches)

    assert len(result) == 2
    assert ("smp", "Show me your plan") in result
    assert ("new", "NewReplacement") in result
    assert ("afk", "away from keyboard") not in result


def test_filter_duplicates_no_existing() -> None:
    """Test filtering when no existing matches."""
    from conjuring.spells.espanso import filter_duplicates

    macos_replacements = [("a", "Apple"), ("b", "Banana")]
    result = filter_duplicates(macos_replacements, set())

    assert len(result) == 2
    assert all(item in result for item in macos_replacements)


def test_write_imported_yml_new_file() -> None:
    """Test writing to new imported.yml file."""
    from conjuring.spells.espanso import write_imported_yml

    with tempfile.TemporaryDirectory() as tmpdir:
        match_dir = Path(tmpdir) / "match"
        match_dir.mkdir()

        write_imported_yml(match_dir, [("tbh", "to be honest"), ("smp", "Show me your plan")])

        imported_file = match_dir / "imported.yml"
        assert imported_file.exists()
        content = imported_file.read_text()
        assert "# Imported from macOS text replacements" in content
        assert "trigger: tbh" in content
        assert "replace: to be honest" in content
        assert "trigger: smp" in content
        assert "replace: Show me your plan" in content
        assert "word: true" in content


def test_write_imported_yml_merge_existing() -> None:
    """Test merging with existing imported.yml file."""
    from conjuring.spells.espanso import write_imported_yml

    with tempfile.TemporaryDirectory() as tmpdir:
        match_dir = Path(tmpdir) / "match"
        match_dir.mkdir()

        (match_dir / "imported.yml").write_text(
            '# Imported from MacOS text replacements\n\nmatches:\n  - trigger: "old"\n    replace: "OldReplacement"\n',
        )

        write_imported_yml(match_dir, [("new", "NewReplacement")])

        content = (match_dir / "imported.yml").read_text()
        assert "old" in content
        assert "trigger: new" in content


def test_write_imported_yml_empty_list() -> None:
    """Test writing empty list doesn't create file."""
    from conjuring.spells.espanso import write_imported_yml

    with tempfile.TemporaryDirectory() as tmpdir:
        match_dir = Path(tmpdir) / "match"
        match_dir.mkdir()
        write_imported_yml(match_dir, [])
        assert not (match_dir / "imported.yml").exists()


def test_import_replacements_integration() -> None:
    """Test complete import flow."""
    from conjuring.spells.espanso import import_replacements

    mock_plist = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<array>
    <dict>
        <key>on</key><string>1</string>
        <key>replace</key><string>tbh</string>
        <key>with</key><string>to be honest</string>
    </dict>
    <dict>
        <key>on</key><string>1</string>
        <key>replace</key><string>new</string>
        <key>with</key><string>NewReplacement</string>
    </dict>
</array>
</plist>"""

    with tempfile.TemporaryDirectory() as tmpdir:
        match_dir = Path(tmpdir) / "match"
        match_dir.mkdir()
        (match_dir / "base.yml").write_text('matches:\n  - trigger: "tbh"\n    replace: "to be honest"\n')

        raw_mock = Mock(returncode=0, stdout=b"raw")
        converted_mock = Mock(returncode=0, stdout=mock_plist)

        with (
            patch("subprocess.run", side_effect=[raw_mock, converted_mock]),
            patch("conjuring.spells.espanso.ESPANSO_MATCH_DIR", match_dir),
        ):
            from invoke import Context

            import_replacements(Context())

        content = (match_dir / "imported.yml").read_text()
        assert "trigger: new" in content
        assert "NewReplacement" in content
        assert "trigger: tbh" not in content
