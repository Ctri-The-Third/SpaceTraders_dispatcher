import setuptools
from spacetraders_v1.__version__ import VERSION

setuptools.setup(
    name="spacetraders",
    version=VERSION,
    description="Python library for SpaceTraders API",
    url="https://github.com/Ctri-The-Third/SpaceTraders",
    author="C'tri",
    author_email="python_packages@ctri.com",
    license="Apache License 2.0",
    packages=["spacetraders"],
    package_dir={"spacetraders": "spacetraders_v2"},
    classifiers=["Programming Language :: Python :: 3.10"],
    install_requires=["requests==2.31.0"],
    python_requires=">=3.10",
)
