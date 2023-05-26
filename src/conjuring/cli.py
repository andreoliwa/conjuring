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
from enum import Enum
from pathlib import Path
from string import Template
from textwrap import dedent

import typer
from ruamel.yaml import YAML

from conjuring.constants import CONJURING_INIT, ROOT_INVOKE_YAML
from conjuring.grimoire import print_error, print_success, print_warning

KEY_TASKS = "tasks"
KEY_COLLECTION_NAME = "collection_name"

app = typer.Typer(no_args_is_help=True)


@app.callback()
def conjuring() -> None:
    """Conjuring: Reusable global Invoke tasks that can be merged with local project tasks."""


class Mode(str, Enum):
    """Which spells to include in the root config file."""

    opt_in = "opt-in"
    opt_out = "opt-out"
    all_ = "all"


@app.command()
def init(mode: Mode = Mode.all_) -> None:
    """Init Invoke to work with Conjuring, merging local `tasks.py` files with global Conjuring tasks."""
    # FIXME[AA]: --import
    # FIXME[AA]: --force
    # FIXME[AA]: iterfzf? it's old, 2020
    if patch_invoke_yaml(ROOT_INVOKE_YAML):
        print_warning(f"File {ROOT_INVOKE_YAML} was configured for Conjuring")
    else:
        print_success(f"File {ROOT_INVOKE_YAML} is already configured for Conjuring")
    generate_conjuring_init(mode)


def patch_invoke_yaml(config_file: Path) -> bool:
    """Patch the root Invoke config file to work with Conjuring."""
    yaml = YAML()

    if not config_file.exists():
        data = yaml.load(f"{KEY_TASKS}:\n  {KEY_COLLECTION_NAME}: {CONJURING_INIT}")
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


def generate_conjuring_init(mode: Mode) -> None:
    """Generate the Conjuring init file."""
    conjuring_init = Path(f"~/{CONJURING_INIT}.py").expanduser()
    python_code = '''
        """Bootstrap file for Conjuring, created by `conjuring init. See https://github.com/andreoliwa/conjuring."""
        from conjuring import Spellbook

        namespace = Spellbook().$function($args)
    '''
    template = Template(dedent(python_code).lstrip())
    if mode == Mode.opt_in:
        contents = template.substitute(function="cast_only", args='"aws*", "k8s*", "pre-commit*", "py*", "*install"')
    elif mode == Mode.opt_out:
        contents = template.substitute(function="cast_all_except", args='"media*", "onedrive*"')
    else:
        contents = template.substitute(function="cast_all", args="")

    if conjuring_init.exists():
        print_error(f"File {conjuring_init} already exists. Use --force to override")
        current = conjuring_init.read_text()
        print_success("Current contents:")
        typer.echo(current)
        print_warning("New contents:")
        typer.echo(contents)
        return

    conjuring_init.write_text(contents)

    print_success(f"File {conjuring_init} was updated")
    typer.echo(contents)
