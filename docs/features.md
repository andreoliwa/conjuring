# Features

## Modes

Conjuring has 3 available modes (all tasks, opt-in and opt-out), detailed below.

When you run `conjuring init`, it creates an `~/.invoke.yaml` file and a
`~/conjuring_init.py` on your home directory.

This will merge any existing local `tasks.py` file with the global
Conjuring tasks.

For more details, read about [default configuration values on Configuration —
Invoke documentation](https://docs.pyinvoke.org/en/stable/concepts/configuration.html#default-configuration-values).

### All tasks

To use all global Conjuring tasks provided by this package, run:

```shell
conjuring init --mode all
```

Run `invoke --list` from any directory, and you will see all Conjuring tasks.

### Opt-in

If you want to only include the global Conjuring tasks you want, run this
command and select the files with [fzf](https://github.com/junegunn/fzf):

```shell
conjuring init --mode opt-in
```

Or you can edit the Python bootstrap file manually. Suppose you only want
these global tasks:

- AWS;
- Kubernetes;
- pre-commit;
- Python;
- all tasks that install anything.

This is how you can do it:

```python
# ~/conjuring_init.py
from conjuring import Spellbook

namespace = Spellbook().cast_only("aws*", "k8s*", "pre-commit*", "py*", "*install")
```

### Opt-out

To use all Conjuring modules and tasks, except for a few, run this
command and select the files with [fzf](https://github.com/junegunn/fzf):

```shell
conjuring init --mode opt-out
```

Or you can edit the Python bootstrap file manually.

Suppose you want all Conjuring tasks except media and OneDrive tasks.
This is the way:

```python
# ~/conjuring_init.py
from conjuring import Spellbook

namespace = Spellbook().cast_all_except("media*", "onedrive*")
```

## Shell enhancements

Invoke can also be configured with environment variables for an even smoother
experience.

Note: this is not a Conjuring feature, it's built-in in Invoke.

### Echo all commands

Echo all commands in all tasks by default, like 'make' does
([documentation](http://docs.pyinvoke.org/en/stable/concepts/configuration.html#basic-rules)):

```shell
# ~/.bashrc, ~/.zshrc or your favourite shell
export INVOKE_RUN_ECHO=1
```

### Coloured output

Use a pseudo-terminal by default (display colored output)
([documentation](http://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run)):

```shell
# ~/.bashrc, ~/.zshrc or your favourite shell
export INVOKE_RUN_PTY=1
```

### Short aliases

Add short aliases for the `invoke` command:

```shell
# ~/.bashrc, ~/.zshrc or your favourite shell
alias i='invoke'
alias il='invoke --list'
alias ih='invoke --help'
alias ir='invoke --dry'
```

### Auto-completion

Follow this quick copy/paste setup to configure auto-completion for Conjuring.
Or read the links below for more details.

To enable completion on terminals, add this to your `~/.bash_profile`:

```shell
# ~/.bash_profile
export BASH_COMPLETION_USER_DIR="$HOME/.local/share/bash-completion"
if [[ -d "$BASH_COMPLETION_USER_DIR/completions" ]]; then
    for COMPLETION in "$BASH_COMPLETION_USER_DIR/completions/"*; do
        source "$COMPLETION"
    done
fi
# https://github.com/tiangolo/typer installs completion files in this directory
if [[ -d "$HOME/.bash_completions/" ]]; then
    for COMPLETION in "$HOME/.bash_completions/"*; do
        [[ -r "$COMPLETION" ]] && source "$COMPLETION"
    done
fi
```

Then run these commands to install auto-completion for Invoke and Conjuring:

```shell
# To get help, run `invoke` or `invoke --help`
invoke --print-completion-script=bash > $BASH_COMPLETION_USER_DIR/completions/invoke.bash-completion

# To get help, run `conjuring` or `conjuring --help`
conjuring --install-completion bash
```

Then open a new terminal, type `invoke <TAB>` or `conjuring <TAB>`,
and you will have auto-completion.

You can even set up auto-completion for aliases (like `i <TAB>` for `invoke`)
with the [complete-alias](https://github.com/cykerway/complete-alias) project.

Some links for more details:

- [Shell tab completion — Invoke documentation](https://docs.pyinvoke.org/en/stable/invoke.html#shell-tab-completion)
- [scop/bash-completion: Programmable completion functions for bash](https://github.com/scop/bash-completion)
- [cykerway/complete-alias: automagical shell alias completion;](https://github.com/cykerway/complete-alias)

## Creating your own reusable tasks

### Add your own custom tasks from Python modules or packages to global tasks

You can create your own Python modules or packages with Invoke tasks, and they
can be added to the global scope and be available from any directory.

- On the init file, call `import_dirs()` with the path to your modules or packages;
- The import method detects if the directory is a Python package or not,
  and imports it accordingly;
- The example uses `cast_all()`, but you can use any of the other `cast_*`
  methods described above ([opt-in](#opt-in)
  or [opt-out](#opt-out)).

```python
# ~/conjuring_init.py
from conjuring import Spellbook

namespace = (
    Spellbook()
    .import_dirs(
        "~/path/to/your/src/my_package",
        "~/path/to/a/some-directory-with-py-files",
    )
    .cast_all()
)
```

### Display your custom task modules conditionally

Some modules under the `spells` directory have a `should_display_tasks` boolean
function to control whether the tasks are displayed or not.

The `conjuring.visibility` module has boolean functions that can be reused by
your modules and tasks.

Example from the `conjuring.spells.git` module:

```python
# /path/to/your_task_module.py
from conjuring.visibility import is_git_repo, ShouldDisplayTasks

should_display_tasks: ShouldDisplayTasks = is_git_repo
```

Other use cases:

- [Poetry](https://github.com/python-poetry/poetry/) tasks: display only when
  there is a `pyproject.toml` in the current dir;
- [pre-commit](https://github.com/pre-commit/pre-commit) tasks: display only
  when there is a `.pre-commit-config.yaml` file in the current dir.

### Display your custom individual tasks conditionally

A task can have its own visibility settings, even if the owner module is
configured to not display tasks.

```python
# /path/to/another_task_module.py
from invoke import task
from conjuring.visibility import MagicTask
from random import randint


@task(klass=MagicTask)
def an_always_visible_task(c):
    """A MagicTask is always visible by default.

    It will always be displayed in every directory,
        regardless of the module ``should_display_tasks()`` function.
    """
    pass


@task(klass=MagicTask, should_display=lambda: bool(randint(0, 1)))
def a_conditionally_visible_task(c):
    """You can use any boolean function to determine visibility."""
    pass
```

Use case:

- you want to group tasks in a module, with a prefix and conditional display of tasks;
- you still want some individual tasks to always be displayed;
- or you want different conditions to display certain tasks.

### Merge your project tasks with the global reusable tasks

Create local `conjuring*.py` files, and they will be merged with the `tasks.py`
in your home dir.
Your project dir can be anywhere under your home dir.

Create two modules with Invoke tasks:

```python
# ~/path/to/project/conjuring_foo.py
from invoke import task


@task
def my_foo(c):
    """My foo task."""
    pass


# ~/path/to/project/conjuring_bar.py
from invoke import task


@task
def my_bar(c):
    """My bar task."""
    pass
```

The task list in your project dir will show tasks from all files, including
the home dir task list.

```shell
$ cd ~/path/to/project/
$ invoke --list
Available tasks:

 my-bar               My bar task.
 my-foo               My foo task.
 <... the global Conjuring tasks will show up here...>
```

### Prefix task names of your custom module

If the module defines this boolean constant with a value of `True`, then the
name of the module will be added as a prefix to tasks.

Example for the `conjuring.spells.pre_commit` module:

```python
SHOULD_PREFIX = True
```

All the tasks of this module will have a `pre-commit.` prefix when you run
`invoke --list`.
