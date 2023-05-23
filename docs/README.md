<!-- markdownlint-disable-file MD031 -->

[//]: # "It breaks numbered lists on Mkdocs"
[//]: # "MD031/blanks-around-fences Fenced code blocks should be surrounded by blank lines"

# Conjuring

Reusable global [Invoke](https://github.com/pyinvoke/invoke) tasks that can be
merged with local project tasks.

## Features

- Merge any local `tasks.py` file with global Conjuring tasks
- Use all global Conjuring tasks provided by this package
- Only include the global Conjuring tasks you want (opt-in mode)
- Use all Conjuring tasks excluding some (opt-out mode)
- Add your own custom tasks from Python modules or packages to global tasks
- Display your custom task modules conditionally
- Display your custom individual tasks conditionally
- Merge your project tasks with the global reusable tasks
- Prefix task names of your custom module

More details on the [features documentation](https://andreoliwa.github.io/conjuring/features/).

## Tasks

Each module under [the `conjuring/spells` directory](https://github.com/andreoliwa/conjuring/tree/master/src/conjuring/spells)
is a collection of Invoke tasks.

## Quick setup

1. Install Conjuring in an isolated virtualenv with [pipx](https://github.com/pypa/pipx):
   ```shell
   pipx install --include-deps conjuring
   ```
   The `--include-deps` flag is needed to install Invoke's apps (`invoke` and `inv`).
2. Create a `tasks.py` file on your home dir:
   ```shell
   echo -e "from conjuring import *\n\nnamespace = cast_all_spells()" > ~/tasks.py
   ```
3. You should see the list of Conjuring tasks from any directory where you type this:
   ```shell
   invoke --list
   ```
