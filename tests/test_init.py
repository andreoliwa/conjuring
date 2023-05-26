from pathlib import Path

from conjuring.cli import patch_invoke_yaml


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
