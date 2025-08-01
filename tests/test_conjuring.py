import os
import sys

import pytest
from invoke import Collection

from conjuring import visibility
from conjuring.grimoire import collection_from_python_files, magically_add_tasks

# so that collection_from_python_files() finds modules under tests/
sys.path.append("tests")


@pytest.fixture
def my_collection() -> Collection:
    return Collection("mine")


def assert_tasks(collection: Collection, task_names: list[str], *, by_name: bool = False) -> None:
    # TODO: fix: something weird in tests: the "collection.tasks" is empty in some cases
    if by_name:
        assert list(collection.task_names.keys()) == task_names
    else:
        assert list(collection.tasks.keys()) == task_names


def test_prefixed_tasks(my_collection: Collection) -> None:
    from tests.fixtures import prefixed  # noqa: PLC0415

    magically_add_tasks(my_collection, prefixed)
    assert_tasks(my_collection, ["prefixed.task-a", "prefixed.task-b"], by_name=True)


def test_add_module_by_name(my_collection: Collection) -> None:
    magically_add_tasks(my_collection, "tests.fixtures.prefixed")
    assert_tasks(my_collection, ["prefixed.task-a", "prefixed.task-b"], by_name=True)


def test_create_collection_from_glob_python_patterns() -> None:
    coll = collection_from_python_files("tests.fixtures.root", "tests/glob*.py")
    assert_tasks(coll, ["glob-c", "glob-d", "root.a", "root.b"], by_name=True)


def test_not_prefixed_tasks(my_collection: Collection) -> None:
    from tests.fixtures import not_prefixed  # noqa: PLC0415

    magically_add_tasks(my_collection, not_prefixed)
    assert_tasks(my_collection, ["task-c", "task-d"])


def test_hide_all(my_collection: Collection) -> None:
    from tests.fixtures import conditional  # noqa: PLC0415

    magically_add_tasks(my_collection, conditional)
    assert_tasks(my_collection, [])


def test_display_all(my_collection: Collection) -> None:
    from tests.fixtures import conditional  # noqa: PLC0415

    os.environ["DISPLAY"] = "yes"
    magically_add_tasks(my_collection, conditional)
    assert_tasks(my_collection, ["task-e", "task-f"])


def test_magic_task_always_visible(my_collection: Collection) -> None:
    from tests.fixtures import magic  # noqa: PLC0415

    magically_add_tasks(my_collection, magic)
    assert_tasks(my_collection, ["this-task-is-always-visible"])


def test_module_with_magic_task(my_collection: Collection) -> None:
    from tests.fixtures import magic  # noqa: PLC0415

    os.environ["INDIVIDUAL"] = "yes"
    magically_add_tasks(my_collection, magic)
    assert_tasks(my_collection, ["depends-on-the-module-config", "this-task-is-always-visible"])


def test_detects_this_project_not_as_poetry_project() -> None:
    """Assumes this project has a valid pyproject.toml."""
    # TODO: add tests for non-poetry projects with pyproject.toml still present
    assert not visibility.is_poetry_project()


@pytest.mark.xfail(reason="Empty collection.tasks is causing this test to fail")
def test_add_task_with_the_same_name(my_collection: Collection) -> None:
    from tests.fixtures import not_prefixed, same  # noqa: PLC0415

    magically_add_tasks(my_collection, not_prefixed)
    magically_add_tasks(my_collection, same)
    assert_tasks(my_collection, ["task-c", "task-d", "task-d-same"])


# TODO: test: add_sub_collection_with_same_name_as_task()
# TODO: test: magic_task_with_its_own_condition_evaluating_to_true()
# TODO: test: magic_task_with_its_own_condition_evaluating_to_false()
