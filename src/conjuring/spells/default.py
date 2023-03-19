"""Default namespace with all the conjuring tasks.

Add it to a ``tasks.py`` file on your home dir:

    from conjuring.spells.default import *

Helpful docs:
- http://www.pyinvoke.org/
- http://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run
"""
import sys

from conjuring.grimoire import collection_from_python_files, magically_add_tasks
from conjuring.spells import (
    aws,
    blanket,
    conjuring,
    docker,
    duplicity,
    fork,
    git,
    jrnl,
    media,
    onedrive,
    paperless,
    pre_commit,
    python,
    shell,
)

__all__ = ["namespace"]

namespace = collection_from_python_files(sys.modules[__name__], "tasks.py", "conjuring*.py")

# TODO: feat: import all "conjuring.spells" submodules dynamically
for module in [
    git,
    pre_commit,
    jrnl,
    duplicity,
    media,
    fork,
    python,
    conjuring,
    aws,
    blanket,
    docker,
    shell,
    paperless,
    onedrive,
]:
    magically_add_tasks(namespace, module)
