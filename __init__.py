"""Directory-plugin entry point used by Hermes' native loader."""

import importlib.util
import sys
from pathlib import Path


_package_dir = Path(__file__).with_name("sdd_hermes")
_package_name = "_hermes_sdd_team_impl"
_spec = importlib.util.spec_from_file_location(
    _package_name,
    _package_dir / "__init__.py",
    submodule_search_locations=[str(_package_dir)],
)
if _spec is None or _spec.loader is None:
    raise ImportError("Hermes SDD implementation package is missing")
_module = importlib.util.module_from_spec(_spec)
sys.modules[_package_name] = _module
_spec.loader.exec_module(_module)
register = _module.register

__all__ = ["register"]
