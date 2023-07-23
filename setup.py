# depreciated, using python-build with a pyproject.toml instead

import setuptools
from setuptools import find_packages

setuptools.setup(
    version="0.2.0",
    packages=find_packages(where="spacetraders_v2"),
    package_dir={
        "": "spacetraders_v2",
        "pg_upserts": "spacetraders_v2\pg_upserts",
    },
    classifiers=["Programming Language :: Python :: 3.10"],
    python_requires=">=3.10",
)
