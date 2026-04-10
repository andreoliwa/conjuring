# Lazy Imports Guide for Invoke Tasks

## Problem

When using PyInvoke, **all task files are imported when you run any invoke command**,
even if you're only executing a single task. This means that heavy imports at the
top of task files slow down every invoke command.

### Performance Impact

**Before lazy imports:**

- `invoke --list`: ~0.70 seconds

**After lazy imports:**

- `invoke --list`: ~0.30 seconds ⚡ **57% faster**

## Solution: Lazy Imports

Move heavy imports **inside the functions** that use them, rather than at the
top of the file.

### Heavy Libraries to Watch For

These libraries are particularly slow to import and should always be lazy-loaded:

- **pandas** (~200-500ms) - Data manipulation
- **requests** (~50-100ms) - HTTP requests
- **typer** (~30-50ms) - CLI framework
- **rich** (~30-50ms) - Terminal formatting
- **yaml/pyyaml** (~20-40ms) - YAML parsing
- **numpy** (~100-200ms) - Numerical computing
- **matplotlib** (~300-500ms) - Plotting
- **django/flask** (~200-400ms) - Web frameworks

### When to Use Lazy Imports

✅ **DO use lazy imports for:**

- Heavy third-party libraries (pandas, requests, etc.)
- Libraries only used in specific tasks
- Libraries with many dependencies
- Optional dependencies

❌ **DON'T use lazy imports for:**

- Standard library imports (pathlib, datetime, json, etc.)
- Lightweight imports (invoke, typing, etc.)
- Imports used across many functions in the file
- Type hints (use TYPE_CHECKING instead)

## Implementation Patterns

### Pattern 1: Simple Function Import

**Before:**

```python
import typer
from invoke import Context, task


@task
def my_task(c: Context) -> None:
    """Do something."""
    typer.echo("Hello!")
```

**After:**

```python
from invoke import Context, task


@task
def my_task(c: Context) -> None:
    """Do something."""
    import typer

    typer.echo("Hello!")
```

### Pattern 2: Type Hints with TYPE_CHECKING

For type hints, use `TYPE_CHECKING` to avoid runtime imports:

**Before:**

```python
import pandas as pd
from invoke import Context, task


def process_data(df: pd.DataFrame) -> pd.DataFrame:
    """Process data."""
    return df.head()
```

**After:**

```python
from typing import TYPE_CHECKING
from invoke import Context, task

if TYPE_CHECKING:
    import pandas as pd


def process_data(df: "pd.DataFrame") -> "pd.DataFrame":
    """Process data."""
    import pandas as pd

    return df.head()
```

### Pattern 3: Multiple Functions Using Same Import

If multiple functions use the same import, add it to each function:

**Before:**

```python
import requests
from invoke import Context, task


@task
def fetch_data(c: Context) -> None:
    """Fetch data."""
    response = requests.get("https://api.example.com")
    print(response.json())


@task
def post_data(c: Context) -> None:
    """Post data."""
    response = requests.post("https://api.example.com", json={})
    print(response.json())
```

**After:**

```python
from invoke import Context, task


@task
def fetch_data(c: Context) -> None:
    """Fetch data."""
    import requests

    response = requests.get("https://api.example.com")
    print(response.json())


@task
def post_data(c: Context) -> None:
    """Post data."""
    import requests

    response = requests.post("https://api.example.com", json={})
    print(response.json())
```

**Note:** Python caches imports, so importing the same module multiple times has
negligible overhead.

### Pattern 4: Helper Functions

For helper functions called by tasks, add the import to the helper:

**Before:**

```python
import pandas as pd
from invoke import Context, task


def _process_csv(path: str) -> pd.DataFrame:
    """Process CSV file."""
    return pd.read_csv(path)


@task
def import_csv(c: Context, path: str) -> None:
    """Import CSV."""
    df = _process_csv(path)
    print(df.head())
```

**After:**

```python
from typing import TYPE_CHECKING
from invoke import Context, task

if TYPE_CHECKING:
    import pandas as pd


def _process_csv(path: str) -> "pd.DataFrame":
    """Process CSV file."""
    import pandas as pd

    return pd.read_csv(path)


@task
def import_csv(c: Context, path: str) -> None:
    """Import CSV."""
    df = _process_csv(path)
    print(df.head())
```

## Linting

The PLC0415 rule ("Import should be at top of file") is disabled globally in
`pyproject.toml` under `[tool.ruff.lint].ignore` because we intentionally use lazy
imports for performance. This means you don't need to add `# noqa: PLC0415` comments
to every lazy import.

## Measuring Import Time

To measure how long a module takes to import:

```bash
python3 -X importtime -c "import pandas" 2>&1 | grep "import time"
```

Or for your entire invoke setup:

```bash
time invoke --list
```

## Best Practices

1. **Profile first**: Use `time invoke --list` to establish a baseline
2. **Target heavy imports**: Focus on libraries that take >20ms to import
3. **Keep it simple**: Don't over-optimize lightweight imports
4. **Test after refactoring**: Ensure tasks still work correctly
5. **Document why**: Add comments explaining why an import is lazy if it's not obvious

## References

- [PEP 690 - Lazy Imports](https://peps.python.org/pep-0690/)
- [Python Import System](https://docs.python.org/3/reference/import.html)
- [Ruff PLC0415 Rule](https://docs.astral.sh/ruff/rules/import-outside-toplevel/)
