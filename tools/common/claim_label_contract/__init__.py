"""Sliced-labeling contract: frozen schemas + pure-stdlib slicing/replay.

This package is explicitly bundled by the producer (and, from step 3 on, the
gate-check) tool units.  It must stay importable with only the standard
library plus ``toolkit.canonical_json`` -- never tree-sitter, never the
``claim_registry`` package.

Modules (import explicitly, e.g. ``from claim_label_contract import schemas``):

* :mod:`schemas` -- closed JSON Schema documents for ``frame-slices/1``,
  ``frame-slice-input/1``, ``slice-proposals/1`` and
  ``proposal-reconciliation/1`` plus a strict stdlib validator for the subset
  of JSON Schema keywords those documents use (unknown keys, wrong scalar
  types and bool-as-integer are rejected).
* :mod:`slicing` -- deterministic slice planning on global unit records:
  recipes, slice ids, payload assembly and cap accounting.
* :mod:`reconciliation` -- deterministic reconciliation of per-slice child
  proposals into one ``claim-proposals/1`` document plus the
  ``proposal-reconciliation/1`` report.
"""

__all__ = ["reconciliation", "schemas", "slicing"]
