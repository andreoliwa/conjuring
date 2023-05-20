# Conjuring

Reusable global [Invoke](https://github.com/pyinvoke/invoke) tasks that can be
merged with local project tasks.

## Features

Click on the links below to see details about each feature:

- [Display modules conditionally](https://andreoliwa.github.io/conjuring/features/#display-modules-conditionally)
- [Display individual tasks conditionally](https://andreoliwa.github.io/conjuring/features/#display-individual-tasks-conditionally)
- [Merge local tasks with the global tasks on the home directory](https://andreoliwa.github.io/conjuring/features/#merge-local-tasks-with-the-global-tasks-on-the-home-directory)
- [Merge any tasks.py with Conjuring tasks](https://andreoliwa.github.io/conjuring/features/#merge-any-taskspy-with-conjuring-tasks)
- [Prefix task names of a module](https://andreoliwa.github.io/conjuring/features/#prefix-task-names-of-a-module)

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
    echo "from conjuring.spells.default import *" > ~/tasks.py
   ```

4. You should see the list of Conjuring tasks from any directory where you type this:

   ```shell
   invoke --list
   ```
