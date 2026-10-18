"""Variables submodel — semantic_id propagation tests.

Verifies that the Variables submodel built from a Resource model
carries the live-data value on each variable: the ``variable`` Property
holds the LIVE data (empty until the first mapping tick), and the ontology
concept URI rides as a supplemental semantic id of that Property (DMP issue
5 — variables carry data as value, semantics as supplemental id, not the
URI as value).

The test builds the current Python-authored Stoppering Resource model.
"""

from __future__ import annotations

import sys
import os

import pytest
from basyx.aas import model

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aas_model import build_from_model  # noqa: E402
from aas_model.resource_instances.stopperingModule import syntegon_stoppering  # noqa: E402


def _find_property(container: model.Submodel, id_short: str) -> model.Property:
    for element in container.submodel_element:
        if isinstance(element, model.Property) and element.id_short == id_short:
            return element
    raise AssertionError(f"Property not found: {container.id_short}.{id_short}")


def _semantic_id_value(ref: model.ExternalReference | None) -> str | None:
    if ref is None:
        return None
    if not ref.key:
        return None
    return ref.key[0].value


def _supplemental_uris(prop: model.Property) -> list[str]:
    uris = []
    for ref in prop.supplemental_semantic_id or []:
        if ref.key:
            uris.append(ref.key[0].value)
    return uris


def _find_variables_submodel(store) -> model.Submodel:
    for obj in store:
        submodels = obj.submodel if hasattr(obj, "submodel") else [obj]
        for sm in submodels:
            if isinstance(sm, model.Submodel) and sm.id_short == "Variables":
                return sm
    raise AssertionError("Variables submodel not found in store")


def test_variables_semantic_id_propagates_to_built_submodel():
    store = build_from_model(syntegon_stoppering())
    variables_sm = _find_variables_submodel(store)

    # Each variable is a direct Property carrying live data; its ontology
    # concept URI rides as a supplemental semantic id, not as the value.
    packml_semantic = _find_property(variables_sm, "PackMLState")
    # the built AAS serializes the initial live-data state as null/absent
    assert packml_semantic.value in (None, "")
    assert "https://w3id.org/2026/apex/semantic/state/operational" \
        in _supplemental_uris(packml_semantic)

    occupation_semantic = _find_property(variables_sm, "OccupationState")
    assert occupation_semantic.value in (None, "")
    assert "https://w3id.org/2026/apex/semantic/state/occupied" \
        in _supplemental_uris(occupation_semantic)
