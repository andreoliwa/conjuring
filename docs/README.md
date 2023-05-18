# Conjuring

Reusable global [Invoke](https://github.com/pyinvoke/invoke) tasks that can be
merged with local project tasks.

## Features

Click on the links below to see details about each feature:

- [Display modules conditionally](features.md#display-modules-conditionally)
- [Display individual tasks conditionally](features.md#display-individual-tasks-conditionally)
- [Merge local tasks with the global tasks on the home directory](features.md#merge-local-tasks-with-the-global-tasks-on-the-home-directory)
- [Merge any tasks.py with Conjuring tasks](features.md#merge-any-taskspy-with-conjuring-tasks)
- [Prefix task names of a module](features.md#prefix-task-names-of-a-module)

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
   # Conjuring doesn't have a PyPI package... yet
   pipx inject invoke git+https://github.com/andreoliwa/conjuring
   ```

3. Create a `tasks.py` file on your home dir:

   ```shell
    echo "from conjuring.spells.default import *" > ~/tasks.py
   ```

4. You should see the list of Conjuring tasks from any directory where you type this:

   ```shell
   invoke --list
   ```
