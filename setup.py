from setuptools import setup, find_packages

setup(
    name="ab_initio_calculations",
    version="0.1.0",
    python_requires=">=3.11",
    packages=find_packages(include=["ab_initio_calculations*"]),
)
