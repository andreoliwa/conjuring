"""Default namespace with all the conjuring tasks.

Add it to a ``tasks.py`` file on your home dir:

    from conjuring.spells.default import *

Helpful docs:
- http://www.pyinvoke.org/
- http://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run
"""
import sys

from conjuring.grimoire import collection_from_python_files, add_tasks_directly
from conjuring.spells import git, pre_commit, jrnl, duplicity, pix, fork, poetry

__all__ = ["namespace"]

namespace = collection_from_python_files(sys.modules[__name__], "tasks.py", "conjuring*.py")

# TODO: import all "conjuring.spells" submodules dynamically
for module in [git, pre_commit, jrnl, duplicity, pix, fork, poetry]:
    add_tasks_directly(namespace, module)
