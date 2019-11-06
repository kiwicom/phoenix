import os
from setuptools import find_packages, setup

with open("requirements.txt") as f:
    install_requires = [line for line in f if line and line[0] not in "#-"]

with open("tests-requirements.txt") as f:
    tests_require = [line for line in f if line and line[0] not in "#-"]

setup(
    name="phoenix",
    version=os.getenv("PACKAGE_VERSION") or "dev",
    url="https://github.com/kiwicom/phoenix",
    author="Dominik Kapisinsky",
    author_email="dominik.kapisinsky@kiwi.com",
    packages=find_packages(),
    install_requires=install_requires,
    tests_require=tests_require,
    include_package_data=True,
    classifiers=[
        "Private :: Do Not Upload",
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
    ],
)
