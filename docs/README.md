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

Read more in [Spells (API reference)](https://andreoliwa.github.io/conjuring/spells/).

## Quick setup

Install Conjuring in an isolated virtualenv with [pipx](https://github.com/pypa/pipx):

```shell
pipx install --include-deps conjuring
```

The `--include-deps` flag is needed to install Invoke's apps (`invoke` and `inv`).

Run the command to configure files on your home directory:

```shell
# For more options:
# conjuring init --help
conjuring init
```

You should see the list of Conjuring tasks from any directory where you type this:

```shell
invoke --list
```

For more configuration options, [read the detailed documentation](https://andreoliwa.github.io/conjuring/features/#modes).
