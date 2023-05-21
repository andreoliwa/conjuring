# Features

## Merge any local `tasks.py` file with global Conjuring tasks

If you create a `tasks.py` in a project, it will override the Conjuring
`tasks.py` on your home dir.
You will only see your local project tasks.

To avoid that, go to your home dir and run:

```shell
invoke conjuring.init
```

This will create an `~/.invoke.yaml` file and rename your main tasks file to `~/conjuring_init.py`.

For more details, read about [default configuration values on Configuration —
Invoke documentation](https://docs.pyinvoke.org/en/stable/concepts/configuration.html#default-configuration-values).

## Use all global Conjuring tasks provided by this package

If you want to use all tasks included in this package, you can import them all.

```python
# ~/conjuring_init.py
from conjuring import Spellbook

namespace = Spellbook().cast_all()
```

Run `invoke --list` from any directory, and you will see all Conjuring tasks.

## Only include the global Conjuring tasks you want (opt-in mode)

You may want to choose which Conjuring modules and tasks you want to use.

Suppose you only want:

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

## Use all Conjuring tasks excluding some (opt-out mode)

You may want to use all Conjuring modules and tasks, except for a few.

Suppose you want all Conjuring tasks except media and OneDrive tasks.
This is the way:

```python
# ~/conjuring_init.py
from conjuring import Spellbook

namespace = Spellbook().cast_all_except("media*", "onedrive*")
```

## Add your own custom tasks from Python modules or packages to global tasks

You can create your own Python modules or packages with Invoke tasks, and they
can be added to the global scope and be available from any directory.

- On the init file, call `import_dirs()` with the path to your modules or packages;
- The import method detects if the directory is a Python package or not,
  and imports it accordingly;
- The example uses `cast_all()`, but you can use any of the other `cast_*`
  methods described above ([opt-in](#only-include-the-global-conjuring-tasks-you-want-opt-in-mode)
  or [opt-out](#use-all-conjuring-tasks-excluding-some-opt-out-mode)).

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

## Display your custom task modules conditionally

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

## Display your custom individual tasks conditionally

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

## Merge your project tasks with the global reusable tasks

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

## Prefix task names of your custom module

If the module defines this boolean constant with a value of `True`, then the
name of the module will be added as a prefix to tasks.

Example for the `conjuring.spells.pre_commit` module:

```python
SHOULD_PREFIX = True
```

All the tasks of this module will have a `pre-commit.` prefix when you run
`invoke --list`.
