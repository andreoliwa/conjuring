"""Default namespace with no tasks, but setting up the magic.

Add it to a ``tasks.py`` file on your home dir:

    from conjuring.spells.empty import *

Helpful docs:
- http://www.pyinvoke.org/
- http://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run
"""
import sys

from conjuring.grimoire import collection_from_python_files

__all__ = ["namespace"]

namespace = collection_from_python_files(sys.modules[__name__], "tasks.py", "conjuring*.py")
