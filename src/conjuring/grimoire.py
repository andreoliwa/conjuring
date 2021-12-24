import os
import sys
import types
from collections import defaultdict
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import List, Set, Dict, Union, Optional

from invoke import Context, Collection

from conjuring.colors import COLOR_LIGHT_RED, COLOR_NONE

CONJURING_IGNORE_MODULES = os.environ.get("CONJURING_IGNORE_MODULES", "").split(",")


def join_pieces(*pieces: str):
    """Join pieces, ignoring empty strings."""
    return " ".join(str(piece) for piece in pieces if str(piece).strip())


def run_command(c: Context, *pieces: str, warn: bool = False, hide: bool = False, dry: bool = None):
    """Build command from pieces, ignoring empty strings."""
    kwargs = {"dry": dry} if dry is not None else {}
    return c.run(join_pieces(*pieces), warn=warn, hide=hide, **kwargs)


def run_stdout(c: Context, *pieces: str, hide=True, **kwargs) -> str:
    """Run a (hidden) command and return the stripped stdout."""
    return c.run(join_pieces(*pieces), hide=hide, pty=False, **kwargs).stdout.strip()


def run_lines(c: Context, *pieces: str) -> List[str]:
    """Run a (hidden) command and return the result as lines."""
    return run_stdout(c, *pieces).splitlines()


def print_error(*message: str):
    """Print an error message."""
    all_messages = " ".join(message)
    print(f"{COLOR_LIGHT_RED}{all_messages}{COLOR_NONE}")


def run_with_fzf(c: Context, *pieces: str, query="", **kwargs) -> str:
    """Run a command with fzf and return the chosen entry."""
    fzf_pieces = ["| fzf --reverse --select-1 --height 40%"]
    if query:
        fzf_pieces.append(f"-q '{query}'")
    kwargs.setdefault("hide", False)
    return run_stdout(c, *pieces, *fzf_pieces, **kwargs)


def ignore_module(module_name: str) -> bool:
    """Ignore a module by its name."""
    for ignore_str in CONJURING_IGNORE_MODULES:
        if ignore_str and ignore_str in module_name:
            return True
    return False


def resolve_module_str(module_or_str: Union[types.ModuleType, str]) -> Optional[types.ModuleType]:
    if isinstance(module_or_str, str):
        module = import_module(module_or_str)
        if ignore_module(module_or_str):
            return None
    else:
        module = module_or_str
        if ignore_module(module.__name__):
            return None
    return module


def slugify(name: str) -> str:
    return name.replace(".", "_")


@dataclass
class SpellBook:
    prefix: str
    module: types.ModuleType
    display_all_tasks: bool


def magically_add_tasks(to_collection: Collection, from_module_or_str: Union[types.ModuleType, str]) -> None:
    """Magically add tasks to the collection according to the module configuration.

    1. If the module has a ``should_display_tasks()`` function,
        it determines if the module is visible in the current directory.
    2. If the module has a ``SHOULD_PREFIX`` boolean variable defined,
        then the tasks will be added to the collection with a prefix.
    """
    resolved_module = resolve_module_str(from_module_or_str)
    prefixed_spell_books: Dict[str, List[SpellBook]] = defaultdict(list)

    sub_collection = Collection.from_module(resolved_module)
    for t in sub_collection.tasks.values():
        task_module = import_module(t.__module__)
        should_display_tasks = getattr(task_module, "should_display_tasks", lambda: True)
        display_all_tasks = should_display_tasks()
        if not display_all_tasks:
            continue

        use_prefix: bool = getattr(task_module, "SHOULD_PREFIX", False)
        if use_prefix:
            # The module should have a prefix: add it later as a sub-collection of the main collection
            prefix = task_module.__name__.split(".")[-1]
            prefixed_spell_books[prefix].append(SpellBook(prefix, task_module, display_all_tasks))
            continue

        if t.name in to_collection.tasks:
            # Task already exists with the same name: add a suffix
            clean_name = slugify(resolved_module.__name__)
            to_collection.add_task(t, f"{t.name}-{clean_name}")
        else:
            # The module doesn't have a prefix: add the task directly
            to_collection.add_task(t)

    for prefix, spell_book_set in prefixed_spell_books.items():
        for spell_book in spell_book_set:
            try:
                to_collection.add_collection(spell_book.module, prefix)
            except ValueError as err:
                if "this collection has a task name" in str(err):
                    to_collection.add_collection(spell_book.module, prefix + "_" + slugify(spell_book.module.__name__))
                    continue
                raise


def collection_from_python_files(current_module, *py_glob_patterns: str):
    """Create a custom collection by adding tasks from multiple files.

    Search directories for glob patterns:
    1. Root dir.
    2. Current dir.

    If the current dir is the root, tasks won't be duplicated.
    """
    # https://docs.python.org/3/library/os.html#os.stat_result
    current_inode = Path(__file__).stat().st_ino

    unique_patterns = set(py_glob_patterns)
    search_dirs: Set[Path] = {Path.cwd(), Path.home()}

    main_colllection = Collection()

    for which_dir in search_dirs:
        sys.path.insert(0, str(which_dir))
        for pattern in unique_patterns:
            for file in which_dir.glob(pattern):
                if file.stat().st_ino == current_inode:
                    # Don't add this file twice
                    continue
                magically_add_tasks(main_colllection, file.stem)
        sys.path.pop(0)

    magically_add_tasks(main_colllection, current_module)

    return main_colllection
