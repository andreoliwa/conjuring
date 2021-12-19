import os
import sys
from importlib import import_module
from pathlib import Path
from typing import List, Set

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


def run_stdout(c: Context, *pieces: str, hide=True) -> str:
    """Run a (hidden) command and return the stripped stdout."""
    return c.run(join_pieces(*pieces), hide=hide, pty=False).stdout.strip()


def run_lines(c: Context, *pieces: str) -> List[str]:
    """Run a (hidden) command and return the result as lines."""
    return run_stdout(c, *pieces).splitlines()


def print_error(*message: str):
    """Print an error message."""
    all_messages = " ".join(message)
    print(f"{COLOR_LIGHT_RED}{all_messages}{COLOR_NONE}")


def run_with_fzf(c: Context, *pieces: str, query="") -> str:
    """Run a command with fzf and return the chosen entry."""
    fzf_pieces = ["| fzf --reverse --select-1 --height 40%"]
    if query:
        fzf_pieces.append(f"-q '{query}'")
    return run_stdout(c, *pieces, *fzf_pieces, hide=False)


def ignore_module(module_name: str) -> bool:
    """Ignore a module by its name."""
    for ignore_str in CONJURING_IGNORE_MODULES:
        if ignore_str and ignore_str in module_name:
            return True
    return False


def add_tasks_directly(main_collection: Collection, module_path):
    """Add tasks directly to the collection, without prefix."""
    if isinstance(module_path, str):
        module = import_module(module_path)
        if ignore_module(module_path):
            return
    else:
        module = module_path
        if ignore_module(module.__name__):
            return
    sub_collection = Collection.from_module(module)
    for t in sub_collection.tasks.values():
        if t.name in main_collection.tasks:
            # Task already exists with the same name: add a suffix
            clean_name = module.__name__.strip("-_")
            main_collection.add_task(t, f"{t.name}-{clean_name}")
        else:
            main_collection.add_task(t)


def collection_from_modules(*glob_patterns: str, prefix_root=False):
    """Create a custom collection by adding tasks from multiple files.

    Search directories for glob patterns:
    1. Root dir.
    2. Current dir.

    If the current dir is the root, tasks won't be duplicated.
    """
    # https://docs.python.org/3/library/os.html#os.stat_result
    current_inode = Path(__file__).stat().st_ino

    unique_patterns = set(glob_patterns)
    search_dirs: Set[Path] = {Path.cwd(), Path.home()}

    main_col = Collection()

    for which_dir in search_dirs:
        sys.path.insert(0, str(which_dir))
        for pattern in unique_patterns:
            for file in which_dir.glob(pattern):
                if file.stat().st_ino == current_inode:
                    # Don't add this file twice
                    continue
                add_tasks_directly(main_col, file.stem)
        sys.path.pop(0)

    if prefix_root:
        main_col.add_collection(Collection.from_module(sys.modules[__name__]), "root")
    else:
        add_tasks_directly(main_col, sys.modules[__name__])

    return main_col
