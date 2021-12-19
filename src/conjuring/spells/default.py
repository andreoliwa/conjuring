"""Default namespace with all the conjuring tasks.

Add it to a ``tasks.py`` file on your home dir:

    from conjuring.spells.default import *

Helpful docs:
- http://www.pyinvoke.org/
- http://docs.pyinvoke.org/en/stable/api/runners.html#invoke.runners.Runner.run
"""
from conjuring.grimoire import collection_from_modules
from conjuring.spells import git, pre_commit, nitpick, jrnl, duplicity, pix, fork

__all__ = ["namespace"]

namespace = collection_from_modules("tasks.py", "conjuring*.py")

namespace.add_collection(git)
namespace.add_collection(pre_commit)
namespace.add_collection(nitpick)
namespace.add_collection(jrnl)
namespace.add_collection(duplicity)
namespace.add_collection(pix)
namespace.add_collection(fork)
