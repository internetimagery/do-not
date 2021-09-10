from setuptools import setup, find_packages

setup(
    name="donot",
    version='0.1.0',
    packages=find_packages(include=["donot"]),
    python_requires=">=2.7.*, !=3.1.*, !=3.2.*, !=3.3.*",
)
