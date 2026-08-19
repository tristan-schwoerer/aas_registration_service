"""Variables submodel — semantic_id propagation tests (templates flow).

Verifies that the Variables submodel built from a ResourceTypeAAS config
carries the ontology semantic URI (``semantic_id_param``) on each variable.

The test needs a ResourceTypeAAS JSON config.  It defaults to the AP2030-UNS
asset config (this repo is consumed as a submodule at ``Registration_Service/``
in AP2030-UNS); set ``AAS_TEST_CONFIG`` to point at another config, or the
tests are skipped.
"""

from __future__ import annotations

import os
import sys

import pytest
from basyx.aas import model

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "third_party", "aas_pydantic")))

from src.templates.builder import build_from_json  # noqa: E402

CONFIG_PATH = os.environ.get(
    "AAS_TEST_CONFIG",
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "AASDescriptions",
                     "Resource", "configs", "syntegonStoppering.json")
    ),
)

if not os.path.exists(CONFIG_PATH):
    pytest.skip(
        f"AAS test config not found: {CONFIG_PATH} (set AAS_TEST_CONFIG to override)",
        allow_module_level=True,
    )


def _find_collection(container, id_short: str) -> model.SubmodelElementCollection:
    elements = (
        getattr(container, "submodel_element", None)
        or getattr(container, "value", None)
        or []
    )
    for element in elements:
        if isinstance(element, model.SubmodelElementCollection) and element.id_short == id_short:
            return element
    raise AssertionError(f"Collection not found: {id_short}")


def _find_property(collection: model.SubmodelElementCollection, id_short: str) -> model.Property:
    for element in collection.value:
        if isinstance(element, model.Property) and element.id_short == id_short:
            return element
    raise AssertionError(f"Property not found: {collection.id_short}.{id_short}")


def _semantic_id_value(ref: model.ExternalReference | None) -> str | None:
    if ref is None:
        return None
    if not ref.key:
        return None
    return ref.key[0].value


def _find_variables_submodel(store) -> model.Submodel:
    for obj in store:
        submodels = obj.submodel if hasattr(obj, "submodel") else [obj]
        for sm in submodels:
            if isinstance(sm, model.Submodel) and sm.id_short == "Variables":
                return sm
    raise AssertionError("Variables submodel not found in store")


def test_variables_semantic_id_propagates_to_built_submodel():
    store = build_from_json(CONFIG_PATH)
    variables_sm = _find_variables_submodel(store)

    # Single variables are direct parts of the top-level VariableItem: the
    # ``variable`` Property + ``interface_reference`` are direct children (no
    # extra "variable" SMC wrapper).
    packml = _find_collection(variables_sm, "PackMLState")
    packml_semantic = _find_property(packml, "variable")
    assert packml_semantic.value == "https://w3id.org/2026/apex/semantic/state/operational"

    occupation = _find_collection(variables_sm, "OccupationState")
    occupation_semantic = _find_property(occupation, "variable")
    assert occupation_semantic.value == "https://w3id.org/2026/apex/semantic/state/occupied"
