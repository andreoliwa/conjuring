# Conjuring

Reusable global [Invoke](https://github.com/pyinvoke/invoke) tasks that can be
merged with local project tasks.

## Features

- Merge any local `tasks.py` file with global Conjuring tasks
- Use all global Conjuring tasks provided by this package
- Only include the global Conjuring tasks you want (opt-in mode)
- Use all Conjuring tasks excluding some (opt-out mode)
- Display your custom task modules conditionally
- Display your custom individual tasks conditionally
- Merge your project tasks with the global reusable tasks
- Prefix task names of your custom module

More details on the [features documentation](https://andreoliwa.github.io/conjuring/features/).

## Tasks

Each module under [the `conjuring/spells` directory](https://github.com/andreoliwa/conjuring/tree/master/src/conjuring/spells)
is a collection of Invoke tasks.

## Quick setup

1. Install invoke in an isolated virtualenv with [pipx](https://github.com/pypa/pipx):

   ```shell
   pipx install invoke
   ```

2. Install Conjuring from GitHub, injecting it directly into the isolated virtualenv:

   ```shell
   pipx inject invoke conjuring
   ```

3. Create a `tasks.py` file on your home dir:

   ```shell
   echo -e "from conjuring import *\n\nnamespace = cast_all_spells()" > ~/tasks.py
   ```

4. You should see the list of Conjuring tasks from any directory where you type this:

   ```shell
   invoke --list
   ```
