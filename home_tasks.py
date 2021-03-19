"""Load invoke tasks for the home directory and from the current dir.

Helpful docs:
- http://www.pyinvoke.org/
- http://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run
"""
from importlib import import_module
from typing import Set
from invoke import task, run, Exit, Collection
from pathlib import Path
import sys

COLOR_NONE = "\033[0m"
COLOR_CYAN = "\033[36m"
COLOR_LIGHT_GREEN = "\033[1;32m"
COLOR_LIGHT_RED = "\033[1;31m"


def branch_name():
    return run("git rev-parse --abbrev-ref HEAD", hide=True).stdout.strip()


@task
def fixme(c):
    """Display FIXME comments, sorted by file and with the branch name at the end."""
    cwd = str(Path.cwd())
    c.run(
        f"rg --line-number -o 'FIXME\[AA\].+' {cwd} | sort -u | sed -E 's/FIXME\[AA\]://'"
        f" | cut -b {len(cwd)+2}- | sed 's/^/{branch_name()}: /'"
    )


@task
def super_up_bclean(c, group=""):
    """Run gita super to update and clean branches."""
    parts = ["gita", "super"]
    if group:
        parts.append(group)
    cmd = " ".join(parts)
    c.run(f"{cmd} up && {cmd} bclean")


def add_tasks_directly(main_collection: Collection, module_path):
    """Add tasks directly to the collection, without prefix."""
    if isinstance(module_path, str):
        module = import_module(module_path)
    else:
        module = module_path
    sub_collection = Collection.from_module(module)
    for t in sub_collection.tasks.values():
        if t.name in main_collection.tasks:
            # Task already exists with the same name: add a suffix
            clean_name = module.__name__.strip("-_")
            main_collection.add_task(t, f"{t.name}-{clean_name}")
        else:
            main_collection.add_task(t)


def collection_from(*glob_patterns: str, prefix_root=False):
    """Create a custom collection by adding tasks from multiple files.

    Search directories for glob patterns:
    1. Root dir.
    2. Current dir.

    If the current dir is the root, tasks won't be duplicated.
    """
    search_dirs: Set[Path] = {Path.cwd(), Path.home()}

    main_col = Collection()

    for which_dir in search_dirs:
        sys.path.insert(0, str(which_dir))
        for pattern in glob_patterns:
            for file in which_dir.glob(pattern):
                add_tasks_directly(main_col, file.stem)
        sys.path.pop(0)

    if prefix_root:
        main_col.add_collection(Collection.from_module(sys.modules[__name__]), "root")
    else:
        add_tasks_directly(main_col, sys.modules[__name__])

    return main_col


namespace = collection_from("tasks.py", "_invoke*.py")
