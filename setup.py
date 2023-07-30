# depreciated, using python-build with a pyproject.toml instead

import setuptools
from setuptools import find_packages

setuptools.setup(
    version="0.2.0",
    packages=find_packages(where="straders_sdk"),
    package_dir={
        "": "straders_sdk",
        "pg_upserts": "straders_sdk\pg_upserts",
    },
    classifiers=["Programming Language :: Python :: 3.10"],
    python_requires=">=3.10",
)
