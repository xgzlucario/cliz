#!/usr/bin/env python3
"""
Development entry point for the cliz application.

This file is a convenience script for running the application during development.
For production use, please install the package and use the 'cliz' command that will
be installed by the package installation process as defined in pyproject.toml:
    [project.scripts]
    cliz = "src.cliz.main:main"
"""

from src.cliz.main import main

if __name__ == "__main__":
    exit(main())