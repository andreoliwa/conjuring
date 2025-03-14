"""Module that contains the command line app.

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -mconjuring` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``conjuring.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``conjuring.__main__`` in ``sys.modules``.

  Also see (1) from http://click.pocoo.org/5/setuptools/#setuptools-integration
"""

import os
import tempfile
from enum import Enum
from pathlib import Path
from shutil import which
from string import Template
from textwrap import dedent

import typer
from invoke import Context
from iterfzf import iterfzf
from ruamel.yaml import YAML

from conjuring.constants import CONJURING_INIT, CONJURING_SPELLS_DIR, ROOT_INVOKE_YAML
from conjuring.grimoire import print_error, print_success, print_warning

KEY_TASKS = "tasks"
KEY_COLLECTION_NAME = "collection_name"
CONJURING_INIT_PY_PATH = Path(f"~/{CONJURING_INIT}.py").expanduser()

app = typer.Typer(no_args_is_help=True)


@app.callback()
def conjuring() -> None:
    """Conjuring: Reusable global Invoke tasks that can be merged with local project tasks."""


class SpellMode(str, Enum):
    """Which spells to include in the root config file."""

    OPT_IN = "opt-in"
    OPT_OUT = "opt-out"
    ALL = "all"
    IMPORTED = "imported"


@app.command()
def init(
    mode: SpellMode = typer.Option(
        SpellMode.ALL,
        "--mode",
        "-m",
        help="Which type of spells to use in the root config file",
    ),
    dir_: list[Path] = typer.Option(
        None,
        "--dir",
        "-d",
        help="Path to a directory with Python packages or modules containing Invoke tasks to import as global tasks",
        exists=True,
        dir_okay=True,
        file_okay=False,
        readable=True,
    ),
    spells: list[str] = typer.Option(
        None,
        "--spells",
        "-s",
        help="List of spells to include/exclude in the global tasks, according to the selected type",
    ),
    force: bool = typer.Option(False, help=f"Overwrite {CONJURING_INIT_PY_PATH} if it exists"),
) -> None:
    """Init Invoke to work with Conjuring, merging local `tasks.py` files with global Conjuring tasks."""
    if patch_invoke_yaml(ROOT_INVOKE_YAML):
        print_warning(f"File {ROOT_INVOKE_YAML} was configured for Conjuring")
    else:
        print_success(f"File {ROOT_INVOKE_YAML} is already configured for Conjuring")

    output = generate_conjuring_init(CONJURING_INIT_PY_PATH, mode, dir_, spells, force)
    if output:
        typer.echo(output)


def patch_invoke_yaml(config_file: Path) -> bool:
    """Patch the root Invoke config file to work with Conjuring."""
    yaml = YAML()

    if not config_file.exists():
        data = yaml.load(f"{KEY_TASKS}:{os.linesep}  {KEY_COLLECTION_NAME}: {CONJURING_INIT}")
        yaml.dump(data, config_file)
        return True

    data = yaml.load(config_file)
    yaml.indent(mapping=2, sequence=4, offset=2)
    tasks = data.get(KEY_TASKS, {})
    current_collection_name = tasks.get(KEY_COLLECTION_NAME)
    if current_collection_name == CONJURING_INIT:
        return False

    if tasks:
        tasks[KEY_COLLECTION_NAME] = CONJURING_INIT
    else:
        data.setdefault(KEY_TASKS, {KEY_COLLECTION_NAME: CONJURING_INIT})
    yaml.dump(data, config_file)
    return True


def generate_conjuring_init(
    path: Path,
    mode: SpellMode,
    import_dirs: list[Path],
    spells: list[str],
    force: bool,
) -> str:
    """Generate the Conjuring init file. Return True if the file is correct, False otherwise."""
    python_code = '''
        """Bootstrap file for Conjuring, created with the `conjuring init` command https://github.com/andreoliwa/conjuring."""
        from conjuring import Spellbook

        namespace = Spellbook()${import_dirs}.${function}(${args})
    '''
    template = Template(dedent(python_code).lstrip())

    import_dirs_call = ""
    if import_dirs:
        flat_list = "\n".join([f'    "{dir_}",' for dir_ in import_dirs])
        import_dirs_call = f".import_dirs(\n{flat_list}\n)"

    if mode == SpellMode.ALL:
        contents = template.substitute(import_dirs=import_dirs_call, function="conjure_all", args="")
    else:
        chosen = spells or []
        prompt = None
        if mode == SpellMode.OPT_IN:
            function_name = "conjure_only"
            prompt = "opt-in: choose the spells to add to global tasks"
        elif mode == SpellMode.OPT_OUT:
            function_name = "conjure_all_except"
            prompt = "opt-out: choose the spells to remove from global tasks: "
        else:
            function_name = "conjure_imported_only"

        if not chosen and prompt:
            spell_names = sorted(
                [file.stem for file in CONJURING_SPELLS_DIR.glob("*.py") if not file.stem.startswith("_")],
            )
            chosen = iterfzf(
                spell_names,
                multi=True,
                prompt=f"conjuring init {prompt}",
                executable=which("fzf"),
            )

        # If nothing still chosen with fzf, quit
        if not chosen:
            raise typer.Abort

        with_stars = sorted(f'    "{spell}*",' for spell in chosen)
        contents = template.substitute(
            import_dirs=import_dirs_call,
            function=function_name,
            args=os.linesep + os.linesep.join(with_stars) + os.linesep,
        )

    if path.exists() and not force:
        fancy_option = "| diff-so-fancy" if which("diff-so-fancy") else ""

        # For some reason, calling Context().run(...) doesn't work; maybe because it's inside the "with" block?
        context = Context()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=True, dir=Path().home()) as temp_file:
            temp_file.write(contents)
            temp_file.flush()
            result = context.run(
                f"diff -u {path} {temp_file.name}{fancy_option}",
                hide=True,
                warn=True,
            )
            if result.stdout:
                print_error(f"File {path} already exists. Use --force to override")
                return result.stdout

            print_success(f"File {path} is already updated")
            return ""

    path.write_text(contents)

    print_success(f"File {path} was updated")
    return contents
