import os
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock

import pytest

from conjuring.cli import SpellMode, generate_conjuring_init, patch_invoke_yaml


def test_file_doesnt_exist(datadir: Path) -> None:
    file: Path = datadir / "non-existent.yaml"
    default: Path = datadir / "default.yaml"
    assert not file.exists()
    assert patch_invoke_yaml(file)
    assert file.read_text() == default.read_text()


def test_already_correct(datadir: Path) -> None:
    file: Path = datadir / "unchanged.yaml"
    previous_content = file.read_text()
    assert not patch_invoke_yaml(file)
    assert file.read_text() == previous_content


def test_file_with_wrong_value(datadir: Path) -> None:
    file: Path = datadir / "wrong-value.yaml"
    right: Path = datadir / "right-value.yaml"
    assert patch_invoke_yaml(file)
    assert file.read_text() == right.read_text()


def test_file_without_tasks(datadir: Path) -> None:
    file: Path = datadir / "no-tasks.yaml"
    with_tasks: Path = datadir / "with-tasks.yaml"
    assert patch_invoke_yaml(file)
    assert file.read_text() == with_tasks.read_text()


@pytest.fixture
def mock_fzf(mocker: Mock) -> Mock:
    mocked_method = mocker.patch("conjuring.cli.iterfzf")
    mocked_method.return_value = ["abc", "def", "ghi"]
    return mocked_method


@pytest.mark.parametrize(
    ("mode", "function_call"),
    [
        (SpellMode.ALL, "conjure_all()" + os.linesep),
        (
            SpellMode.OPT_IN,
            """
            conjure_only(
                "abc*",
                "def*",
                "ghi*",
            )
            """,
        ),
        (
            SpellMode.OPT_OUT,
            """
            conjure_all_except(
                "abc*",
                "def*",
                "ghi*",
            )
            """,
        ),
    ],
)
def test_spells(datadir: Path, mode: SpellMode, function_call: str, mock_fzf: Mock) -> None:
    assert mock_fzf
    file: Path = datadir / "root.py"
    assert not file.exists()
    assert generate_conjuring_init(file, mode, [], [], False)

    expected = '''
        """Bootstrap file for Conjuring, created with the `conjuring init` command https://github.com/andreoliwa/conjuring."""
        from conjuring import Spellbook

        namespace = Spellbook().
    '''
    assert file.read_text() == dedent(expected).strip() + dedent(function_call).lstrip()


def test_import_dirs(datadir: Path) -> None:
    file: Path = datadir / "root.py"
    assert not file.exists()
    package: Path = datadir / "my_package"
    assert generate_conjuring_init(file, SpellMode.ALL, [datadir, package], [], False)

    expected = f'''
        """Bootstrap file for Conjuring, created with the `conjuring init` command https://github.com/andreoliwa/conjuring."""
        from conjuring import Spellbook

        namespace = Spellbook().import_dirs(
            "{datadir}",
            "{package}",
        ).conjure_all()
    '''
    assert file.read_text() == dedent(expected).lstrip()


def test_file_exists(datadir: Path, mock_fzf: Mock) -> None:
    assert mock_fzf
    file: Path = datadir / "root.py"
    assert not file.exists()
    output = generate_conjuring_init(file, SpellMode.ALL, [], [], False)
    assert output == file.read_text()

    assert not generate_conjuring_init(file, SpellMode.ALL, [], [], False)

    output = generate_conjuring_init(file, SpellMode.OPT_IN, [], [], False)
    assert "conjure_only(" in output
