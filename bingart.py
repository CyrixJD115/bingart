#!/usr/bin/env python3
import sys
import os
import importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_dir = os.path.join(_here, "bingart")

spec = importlib.util.spec_from_file_location(
    "bingart",
    os.path.join(_pkg_dir, "__init__.py"),
    submodule_search_locations=[_pkg_dir],
)
pkg = importlib.util.module_from_spec(spec)
sys.modules["bingart"] = pkg
spec.loader.exec_module(pkg)

from bingart.cli import main

main()
