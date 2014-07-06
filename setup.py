from setuptools import setup, find_packages


PACKAGE_NAME = "reviewbotpmd"
VERSION = "0.1"


setup(
    name=PACKAGE_NAME,
    version=VERSION,
    description=("A Review Bot tool that runs PMD, "
                 "a rule-set based source code analyzer that identifies "
                 "potential problems"),
    author="Jeremie Jost",
    author_email="jeremiejost@gmail.com",
    packages=find_packages(),
    entry_points={
        'reviewbot.tools': [
            'pmd = reviewbotpmd.pmd:PMDTool',
        ],
    },
    install_requires=[
        'reviewbot',
    ], )

