"""claim_registry - minimal pilot producer for cure-light PR-text claim chunking.

Modules:

* :mod:`claim_registry.frame` - deterministic atomic-unit walker
* :mod:`claim_registry.capture` - verbatim capture + content identity
* :mod:`claim_registry.canonical` - ``claim-json/1`` canonical serialization
* :mod:`claim_registry.registry` - registry assembly + ownership/witness
* :mod:`claim_registry.validator` - independent recompute/validation
* :mod:`claim_registry.windows` - bounded ingestion windows
* :mod:`claim_registry.tool_manifest` - static ``tool-unit/1`` manifest
* :mod:`claim_registry.cli` - thin CLI

Heavy submodules (tree-sitter) are imported lazily so ``--describe`` and
``--help`` work before dependencies are installed.
"""

from __future__ import annotations

import importlib

__version__ = "0.2.0"

#: public name -> defining submodule (lazy import keeps the package import
#: light; ``from claim_registry import frame_source`` still works normally).
_EXPORTS = {
    "SourceCapture": "capture",
    "capture_bytes": "capture",
    "capture_file": "capture",
    "make_source_ref": "capture",
    "percent_encode": "capture",
    "raw_sha256": "capture",
    "synthetic_git_blob_oid": "capture",
    "ExtractionError": "frame",
    "Frame": "frame",
    "Unit": "frame",
    "frame_file": "frame",
    "frame_recipe": "frame",
    "frame_source": "frame",
    "DEFAULT_WINDOW_RECIPE": "registry",
    "AssemblyResult": "registry",
    "RegistryAssemblyError": "registry",
    "assemble_registry": "registry",
    "default_proposals": "registry",
    "ValidationReport": "validator",
    "validate_registry": "validator",
    "OversizedUnitError": "windows",
    "Window": "windows",
    "WindowRecipeError": "windows",
    "build_windows": "windows",
    "validate_windows": "windows",
    "window_recipe": "windows",
}


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f".{module_name}", __name__), name)
    globals()[name] = value  # cache for subsequent lookups
    return value


__all__ = [
    "AssemblyResult",
    "DEFAULT_WINDOW_RECIPE",
    "ExtractionError",
    "Frame",
    "OversizedUnitError",
    "RegistryAssemblyError",
    "SourceCapture",
    "Unit",
    "ValidationReport",
    "Window",
    "WindowRecipeError",
    "__version__",
    "assemble_registry",
    "build_windows",
    "capture_bytes",
    "capture_file",
    "default_proposals",
    "frame_file",
    "frame_recipe",
    "frame_source",
    "make_source_ref",
    "percent_encode",
    "raw_sha256",
    "synthetic_git_blob_oid",
    "validate_registry",
    "validate_windows",
    "window_recipe",
]
