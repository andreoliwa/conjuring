"""Helper functions used in other modules."""
from __future__ import annotations

import fnmatch
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from shlex import quote
from shutil import which
from typing import TYPE_CHECKING, Callable

import typer
from invoke import Collection, Context, Result, Task

from conjuring.colors import COLOR_BOLD_WHITE, COLOR_LIGHT_GREEN, COLOR_LIGHT_RED, COLOR_NONE, COLOR_YELLOW
from conjuring.visibility import display_task

if TYPE_CHECKING:
    import types
    from collections.abc import Sequence

# TODO: document or remove this variable
CONJURING_IGNORE_MODULES = os.environ.get("CONJURING_IGNORE_MODULES", "").split(",")

REGEX_JIRA = re.compile(r"[A-Z]+-\d+")


def join_pieces(*pieces: str) -> str:
    """Join pieces, ignoring empty strings."""
    return " ".join(str(piece) for piece in pieces if str(piece).strip())


def run_command(c: Context, *pieces: str, dry: bool | None = None, **kwargs: str | bool) -> Result:
    """Build command from pieces, ignoring empty strings."""
    if dry is not None:
        kwargs.setdefault("dry", dry)
    kwargs.setdefault("warn", False)
    kwargs.setdefault("hide", False)
    return c.run(join_pieces(*pieces), **kwargs)


def run_stdout(c: Context, *pieces: str, **kwargs: str | bool) -> str:
    """Run a (hidden) command and return the stripped stdout."""
    kwargs.setdefault("warn", False)
    kwargs.setdefault("hide", True)
    kwargs.setdefault("pty", False)
    return c.run(join_pieces(*pieces), **kwargs).stdout.strip()


def run_lines(c: Context, *pieces: str, **kwargs: str | bool) -> list[str]:
    """Run a (hidden) command and return the result as lines."""
    return run_stdout(c, *pieces, **kwargs).splitlines()


def run_multiple(c: Context, *commands: str, **kwargs: str | bool) -> None:
    """Run multiple commands from a list, ignoring empty ones."""
    for cmd in [c for c in commands if str(c).strip()]:
        c.run(cmd, **kwargs)


def print_color(*message: str, color: str = COLOR_NONE, nl: bool = False) -> None:
    """Print a colored message."""
    all_messages = ("\n" if nl else " ").join(message)
    typer.echo(f"{color}{all_messages}{COLOR_NONE}")


def print_success(*message: str, nl: bool = False) -> None:
    """Print a success message."""
    print_color(*message, color=COLOR_LIGHT_GREEN, nl=nl)


def print_error(*message: str, nl: bool = False) -> None:
    """Print an error message."""
    print_color(*message, color=COLOR_LIGHT_RED, nl=nl)


def print_warning(*message: str, nl: bool = False) -> None:
    """Print a warning message."""
    print_color(*message, color=COLOR_YELLOW, nl=nl)


def ask_user_prompt(*message: str, color: str = COLOR_BOLD_WHITE, allowed_keys: str = "") -> str:
    """Display a prompt with a message. Wait a little before, so stdout is flushed before the input message."""
    lowercase_key_list = [char.lower() for char in allowed_keys] if allowed_keys else []
    options = "/".join(allowed_keys) if allowed_keys else None
    prefix = f"Type {options} +" if allowed_keys else "Press"

    while True:
        typer.echo()
        print_color(*message, color=color)
        time.sleep(0.2)

        typed_input = input(f"{prefix} ENTER to continue or Ctrl-C to abort: ")
        if not allowed_keys:
            return typed_input

        lowercase_key = typed_input.lower()
        if lowercase_key in lowercase_key_list:
            return lowercase_key


# TODO: Use iterfzf or create Fzf class with multi() and single() methods (with different return types
def run_with_fzf(  # noqa: PLR0913
    c: Context,
    *pieces: str,
    query: str = "",
    header: str = "",
    multi: bool = False,
    options: str = "",
    preview: str = "",
    **kwargs: str | bool,
) -> str:
    """Run a command with fzf and return the chosen entry."""
    fzf_pieces = ["| fzf --reverse --select-1 --height 40% --cycle"]
    if query:
        fzf_pieces.append(f"-q '{query}'")
    if header:
        fzf_pieces.append(f"--header='{header}'")
    if multi:
        fzf_pieces.append("--multi")
        which_function: Callable = run_lines
    else:
        which_function = run_stdout
    if options:
        fzf_pieces.append(options)
    if preview:
        fzf_pieces.append(f"--preview={quote(preview)}")
    kwargs.setdefault("hide", False)
    kwargs.setdefault("pty", False)
    return which_function(c, *pieces, *fzf_pieces, **kwargs)


def ignore_module(module_name: str) -> bool:
    """Ignore a module by its name."""
    return any(ignore_str and ignore_str in module_name for ignore_str in CONJURING_IGNORE_MODULES)


def resolve_module_str(module_or_str: types.ModuleType | str) -> types.ModuleType | None:
    """Resolve a module from a string or return it if it's already a module."""
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
    """Slugify a name."""
    return name.replace(".", "_")


def guess_full_task_name(prefix: str | None, name: str) -> str:
    """Guess how Invoke will name this task.

    NOTE: this is unstable and may break because Invoke has no public API to get the final task name.
    """
    formatted_task_name = slugify(name).replace("_", "-")
    return f"{prefix}.{formatted_task_name}" if prefix else formatted_task_name


@dataclass
class PrefixedSpellbook:
    """A collection of Invoke tasks from a module, with a prefix."""

    prefix: str
    module: types.ModuleType
    display_all_tasks: bool


def _is_task_present(name: str, list_: Sequence[str] | None) -> bool:
    if not list_:
        return True
    return any(fnmatch.fnmatch(name, element) for element in list_)


def add_single_task_to(  # noqa: PLR0913
    collection: Collection,
    task: Task,
    include: Sequence[str] | None,
    exclude: Sequence[str] | None,
    *,
    prefix: str | None,
    task_name: str | None,
) -> bool:
    """Add a single task to the collection if it matches the include/exclude filters."""
    guessed_name = guess_full_task_name(prefix, task.name)
    should_include = not include or _is_task_present(guessed_name, include)
    should_exclude = exclude and _is_task_present(guessed_name, exclude)
    if should_include and not should_exclude:
        if task_name:
            collection.add_task(task, task_name)
        else:
            collection.add_task(task)
        return True
    return False


def magically_add_tasks(  # noqa: C901 # TODO: refactor: magically_add_tasks is too complex (12)
    to_collection: Collection,
    from_module_or_str: types.ModuleType | str,
    *,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
) -> None:
    """Magically add tasks to the collection according to the module/task configuration.

    Task-specific configuration has precedence over the module.

    1. If the task is a :py:class:`MagicTask`, then its ``should_display()`` method is used to check visibility.
    2. If the module has a ``should_display_tasks()`` function,
        it determines if the module is visible in the current directory.
    3. If the module has a ``SHOULD_PREFIX`` boolean variable defined,
        then the tasks will be added to the collection with a prefix.
    """
    resolved_module = resolve_module_str(from_module_or_str)
    prefixed_spell_books: dict[str, list[PrefixedSpellbook]] = defaultdict(list)

    sub_collection = Collection.from_module(resolved_module)
    for t in sub_collection.tasks.values():
        task_module = import_module(t.__module__)
        should_display_tasks = getattr(task_module, "should_display_tasks", lambda: True)
        display_all_tasks = should_display_tasks()

        use_prefix: bool = getattr(task_module, "SHOULD_PREFIX", False)
        if use_prefix:
            # The module should have a prefix: add it later as a sub-collection of the main collection
            prefix = task_module.__name__.split(".")[-1]
            prefixed_spell_books[prefix].append(PrefixedSpellbook(prefix, task_module, display_all_tasks))
            continue
        if not display_task(t, display_all_tasks):
            continue

        if t.name in to_collection.tasks and resolved_module:
            # Task already exists with the same name: add a suffix
            clean_name = slugify(resolved_module.__name__)
            new_task_name = f"{t.name}-{clean_name}"
            add_single_task_to(to_collection, t, include, exclude, prefix=None, task_name=new_task_name)
        else:
            # The module doesn't have a prefix: add the task directly
            add_single_task_to(to_collection, t, include, exclude, prefix=None, task_name=None)

    for prefix, spell_book_set in prefixed_spell_books.items():
        for spell_book in spell_book_set:
            sub_collection = Collection()
            for t in Collection.from_module(spell_book.module).tasks.values():
                if display_task(t, spell_book.display_all_tasks):
                    add_single_task_to(sub_collection, t, include, exclude, prefix=prefix, task_name=None)

            try:
                to_collection.add_collection(sub_collection, prefix)
            except ValueError as err:
                if "this collection has a task name" in str(err):
                    to_collection.add_collection(spell_book.module, prefix + "_" + slugify(spell_book.module.__name__))
                    continue
                raise


def collection_from_python_files(
    current_module: types.ModuleType | str,
    *py_glob_patterns: str,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
) -> Collection:
    """Create a custom collection by adding tasks from multiple files.

    Search directories for glob patterns:
    1. Root dir.
    2. Current dir.

    If the current dir is the root, tasks won't be duplicated.
    """
    # https://docs.python.org/3/library/os.html#os.stat_result
    current_inode = Path(__file__).stat().st_ino

    unique_patterns = set(py_glob_patterns)
    search_dirs: set[Path] = {Path.cwd(), Path.home()}

    main_colllection = Collection()

    for which_dir in search_dirs:
        sys.path.insert(0, str(which_dir))
        for pattern in unique_patterns:
            for file in which_dir.glob(pattern):
                if file.stat().st_ino == current_inode:
                    # Don't add this file twice
                    continue
                magically_add_tasks(main_colllection, file.stem, include=include, exclude=exclude)
        sys.path.pop(0)

    magically_add_tasks(main_colllection, current_module, include=include, exclude=exclude)

    return main_colllection


def lazy_env_variable(variable: str, description: str) -> str:
    """Fetch environment variable. On error, display a message with its description."""
    try:
        return os.environ[variable]
    except KeyError as err:
        print_error(f"Set the {variable!r} environment variable with the {description}.")
        raise SystemExit from err


def bat(c: Context, *pieces: str) -> Result:
    """Display files with "bat" if it's installed. Otherwise, fallback to "cat"."""
    tool = "bat" if which("bat") else "cat"
    return run_command(c, tool, *pieces)
