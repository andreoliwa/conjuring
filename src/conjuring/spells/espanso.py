"""Import macOS keyboard text replacements into https://github.com/espanso/espanso configuration."""

import plistlib
import subprocess
from pathlib import Path

from invoke import Context, task

from conjuring.grimoire import ask_yes_no, print_error, print_normal, print_success, print_warning

SHOULD_PREFIX = True

ESPANSO_MATCH_DIR = Path.home() / "Library/Application Support/espanso/match"


def extract_macos_replacements() -> list[tuple[str, str]]:
    """Extract active text replacements from macOS.

    Returns:
        List of (trigger, replacement) tuples for active replacements (on=1).
        Returns empty list if command fails or data cannot be parsed.

    """
    try:
        raw = subprocess.run(
            ["defaults", "read", "-g", "NSUserDictionaryReplacementItems"],  # noqa: S607
            capture_output=True,
            check=False,
        )
        if raw.returncode != 0:
            return []

        converted = subprocess.run(
            ["plutil", "-convert", "xml1", "-o", "-", "-"],  # noqa: S607
            input=raw.stdout,
            capture_output=True,
            check=False,
        )
        if converted.returncode != 0:
            return []

        plist_data = plistlib.loads(converted.stdout)

        replacements = []
        for item in plist_data:
            on_value = item.get("on")
            if on_value in (1, "1", True):
                trigger = item.get("replace", "")
                replacement = item.get("with", "")
                if trigger and replacement:
                    replacements.append((trigger, replacement))

        return replacements  # noqa: TRY300

    except Exception:  # noqa: BLE001
        return []


def scan_existing_espanso_configs(match_dir: Path) -> set[tuple[str, str]]:
    """Scan existing espanso YAML files and extract all matches.

    Args:
        match_dir: Path to espanso match directory

    Returns:
        Set of (trigger, replace) tuples from all YAML files.

    """
    if not match_dir.exists():
        return set()

    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True
    existing_matches: set[tuple[str, str]] = set()

    for yml_file in [*match_dir.rglob("*.yml"), *match_dir.rglob("*.yaml")]:
        try:
            data = yaml.load(yml_file)
            if not data:
                continue
            for match in data.get("matches", []) or []:
                trigger = match.get("trigger", "")
                replace = match.get("replace", "")
                if trigger and replace:
                    existing_matches.add((trigger, replace))
        except Exception:  # noqa: BLE001,S112
            continue

    return existing_matches


def filter_duplicates(
    macos_replacements: list[tuple[str, str]],
    existing_matches: set[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Filter out exact duplicate (trigger, replace) pairs.

    Args:
        macos_replacements: List of macOS replacements
        existing_matches: Set of existing espanso matches

    Returns:
        List of replacements that don't exist as exact matches.

    """
    return [(trigger, replace) for trigger, replace in macos_replacements if (trigger, replace) not in existing_matches]


def write_imported_yml(match_dir: Path, new_replacements: list[tuple[str, str]]) -> None:
    """Write new replacements to imported.yml, merging with existing if present.

    Args:
        match_dir: Path to espanso match directory
        new_replacements: List of (trigger, replace) tuples to write

    """
    if not new_replacements:
        return

    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.preserve_quotes = True

    imported_file = match_dir / "imported.yml"

    existing_entries: list = []
    if imported_file.exists():
        try:
            data = yaml.load(imported_file)
            if data and "matches" in data:
                existing_entries = list(data["matches"])
        except Exception:  # noqa: BLE001,S110
            pass

    existing_set = {(e.get("trigger", ""), e.get("replace", "")) for e in existing_entries}

    all_matches = existing_entries.copy()
    for trigger, replace in new_replacements:
        if (trigger, replace) not in existing_set:
            all_matches.append({"trigger": trigger, "replace": replace, "word": True})

    with imported_file.open("w") as f:
        f.write("# Imported from macOS text replacements\n\n")
        yaml.dump({"matches": all_matches}, f)


@task(name="import")
def import_replacements(c: Context) -> None:
    """Import macOS text replacements into https://github.com/espanso/espanso config.

    1. Reads active macOS text replacements from system preferences
    2. Scans existing espanso config files
    3. Filters out exact duplicates (same trigger + replacement text)
    4. Writes new entries to imported.yml
    """
    print_normal("Extracting macOS text replacements...")
    macos_replacements = extract_macos_replacements()

    if not macos_replacements:
        print_error("Could not read macOS text replacements or none found")
        return

    print_success(f"Found {len(macos_replacements)} macOS text replacements")

    if not ESPANSO_MATCH_DIR.exists():
        print_warning(f"Espanso directory not found: {ESPANSO_MATCH_DIR}")
        if ask_yes_no(f"Create directory {ESPANSO_MATCH_DIR}?"):
            ESPANSO_MATCH_DIR.mkdir(parents=True, exist_ok=True)
            print_success(f"Created {ESPANSO_MATCH_DIR}")
        else:
            print_error("Import cancelled")
            return

    print_normal("Scanning existing espanso configs...")
    existing_matches = scan_existing_espanso_configs(ESPANSO_MATCH_DIR)
    print_success(f"Found {len(existing_matches)} existing espanso matches")

    new_replacements = filter_duplicates(macos_replacements, existing_matches)

    if not new_replacements:
        print_warning("All macOS replacements already exist in espanso")
        return

    skipped = len(macos_replacements) - len(new_replacements)
    print_success(f"Importing {len(new_replacements)} new replacements (skipped {skipped} duplicates)")

    write_imported_yml(ESPANSO_MATCH_DIR, new_replacements)
    print_success(f"Successfully imported to {ESPANSO_MATCH_DIR / 'imported.yml'}")
