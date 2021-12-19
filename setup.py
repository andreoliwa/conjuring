# -*- coding: utf-8 -*-
from setuptools import setup

package_dir = {"": "src"}

packages = ["conjuring", "conjuring.spells"]

package_data = {"": ["*"]}

install_requires = ["invoke>=1.6.0,<2.0.0", "setuptools>=59.6.0,<60.0.0"]

setup_kwargs = {
    "name": "conjuring",
    "version": "0.1.0",
    "description": "",
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
