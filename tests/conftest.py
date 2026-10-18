"""Make ``aas_model`` (the shared package, ADR-016) importable in tests.

``aas-model`` is this repository's submodule; expose its ``src`` layout on the
path so the tests run against the pinned model without installing it.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, ".."))
_AAS_MODEL_SRC = os.path.join(_REPO, "aas-model", "src")

for p in (_AAS_MODEL_SRC,):
    if p not in sys.path and os.path.isdir(p):
        sys.path.insert(0, p)
