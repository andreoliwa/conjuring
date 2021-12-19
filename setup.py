# -*- coding: utf-8 -*-
from setuptools import setup

package_dir = {"": "src"}

packages = ["conjuring", "conjuring.spells"]

package_data = {"": ["*"]}

install_requires = ["invoke"]

setup_kwargs = {
    "name": "conjuring",
    "version": "0.1.0",
    "description": "🐍🤖 Reusable global Invoke tasks that can be merged with local project tasks",
    "long_description": None,
    "author": "W. Augusto Andreoli",
    "author_email": "andreoliwa@gmail.com",
    "maintainer": None,
    "maintainer_email": None,
    "url": None,
    "package_dir": package_dir,
    "packages": packages,
    "package_data": package_data,
    "install_requires": install_requires,
    "python_requires": ">=3.9,<4.0",
}


setup(**setup_kwargs)
