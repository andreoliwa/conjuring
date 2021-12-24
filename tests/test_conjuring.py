import os
from typing import List

import pytest
from invoke import Collection

from conjuring.grimoire import magically_add_tasks, collection_from_python_files


@pytest.fixture
def my_collection():
    return Collection("mine")


def assert_tasks(collection: Collection, tasks: List[str]):
    assert list(collection.task_names.keys()) == tasks


def test_prefixed_tasks(my_collection):
    from tests.fixtures import prefixed

    magically_add_tasks(my_collection, prefixed)
    assert_tasks(my_collection, ["prefixed.task-a", "prefixed.task-b"])


def test_add_module_by_name(my_collection):
    magically_add_tasks(my_collection, "tests.fixtures.prefixed")
    assert_tasks(my_collection, ["prefixed.task-a", "prefixed.task-b"])


def test_create_collection_from_glob_python_patterns():
    coll = collection_from_python_files("tests.fixtures.root", "glob*.py")
    assert_tasks(coll, ["glob-c", "glob-d", "root.a", "root.b"])


def test_not_prefixed_tasks(my_collection):
    from tests.fixtures import not_prefixed

    magically_add_tasks(my_collection, not_prefixed)
    assert_tasks(my_collection, ["task-c", "task-d"])


def test_hide_all(my_collection):
    from tests.fixtures import conditional

    magically_add_tasks(my_collection, conditional)
    assert_tasks(my_collection, [])


def test_display_all(my_collection):
    from tests.fixtures import conditional

    os.environ["DISPLAY"] = "yes"
    magically_add_tasks(my_collection, conditional)
    assert_tasks(my_collection, ["task-e", "task-f"])


def test_magic_task_always_visible(my_collection):
    from tests.fixtures import magic

    magically_add_tasks(my_collection, magic)
    assert_tasks(my_collection, ["this-task-is-always-visible"])


def test_module_with_magic_task(my_collection):
    from tests.fixtures import magic

    os.environ["INDIVIDUAL"] = "yes"
    magically_add_tasks(my_collection, magic)
    assert_tasks(my_collection, ["depends-on-the-module-config", "this-task-is-always-visible"])


def test_add_task_with_the_same_name():
    pass  # TODO:


def test_add_sub_collection_with_same_name_as_task():
    pass  # TODO:


def test_magic_task_with_its_own_condition_evaluating_to_true():
    pass  # TODO:


def test_magic_task_with_its_own_condition_evaluating_to_false():
    pass  # TODO:
