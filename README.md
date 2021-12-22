# Conjuring

Reusable global [Invoke](https://github.com/pyinvoke/invoke) tasks that can be merged with local project tasks.

## Quick setup

1. Install invoke in an isolated virtualenv with [pipx](https://github.com/pypa/pipx):
    ```shell
    pipx install invoke
    ```
2. Install Conjuring from GitHub, injecting it directly into the isolated virtualenv:
    ```shell
    # Conjuring doesn't have a PyPI package... yet
    pipx inject invoke git+https://github.com/andreoliwa/conjuring
    ```
3. Create a `tasks.py` file on your home dir:
   ```shell
    echo "from conjuring.spells.default import *" > ~/tasks.py
    ``` 
4. You should see the list of Conjuring tasks from any directory where you type this:
    ```shell
    inv --list
    ```

## Features

### Display tasks conditionally

Some modules under the `spells` directory have a `should_display_tasks` boolean function to control whether the tasks are displayed or not.

Example for the `conjuring.spells.git` module:
```python
def should_display_tasks() -> bool:
    """Only display tasks if the current dir is a Git repo."""
    return Path(".git").exists()
```

Other examples of usage:

- [Poetry](https://github.com/python-poetry/poetry/) tasks: display only when there is a `pyproject.toml` in the current dir;
- [pre-commit](https://github.com/pre-commit/pre-commit) tasks: display only when there is a ` .pre-commit-config.yaml` file in the current dir. 

### Merge local tasks with the global tasks on the home directory

Create local `conjuring*.py` files and it will be merged with the `tasks.py` in your home dir.
Your project dir can be anywhere under your home dir. 

1. Create `~/path/to/your/project/conjuring_foo.py` with Invoke tasks.
   ```python
   from invoke import task
   
   @task
   def my_foo(c):
        """My foo task."""
        pass
   ```
2. Create another `~/path/to/your/project/conjuring_bar.py` file with more Invoke tasks.
   ```python
   from invoke import task
   
   @task
   def my_bar(c):
        """My bar task."""
        pass
   ```
3. The task list in your project dir will show tasks from all files, including the home dir task list.
   ```shell
   $ cd ~/path/to/your/project/
   $ inv --list
   Available tasks:
   
     my-bar               My bar task.
     my-foo               My foo task.
     <... the Conjuring tasks will show up here...>
   ```

### Merge any tasks.py with Conjuring tasks 

If you create a `tasks.py` in a project, it will override the Conjuring `tasks.py` on your home dir.
You will only see your local project tasks.

To avoid that, go to your home dir and run:

```shell
inv conjuring.setup
```

This will create an `~/.invoke.yaml` file and rename your main tasks file to `~/conjuring_summon.py`.

For more details, read about [default configuration values on Configuration — Invoke documentation](https://docs.pyinvoke.org/en/stable/concepts/configuration.html#default-configuration-values). 

### Prefix task names of a module

If the module defines this boolean constant with a value of `True`, then the name of the module will be added as a prefix to tasks.

Example for the `conjuring.spells.pre_commit` module:

```python
SHOULD_PREFIX = True
```

All the tasks of this module will have a `pre-commit.` prefix when you run `inv --list`.

## Related Projects

- [pyinvoke/invoke: Pythonic task management & command execution.](https://github.com/pyinvoke/invoke)
- [pyinvoke/invocations: Reusable Invoke tasks](https://github.com/pyinvoke/invocations)
- [jhermann/rituals: Project automation task library for ‘Invoke’ tasks that are needed again and again.](https://github.com/jhermann/rituals)
