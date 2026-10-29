"""Skill operations + AIMC skill mappings — Resource model tests.

Verifies the operation-delegation wiring added to the Resource AAS:

- CCI skills carry an ``operation`` (AAS Operation) with an
  ``invocationDelegation`` qualifier pointing at the generated REST endpoint,
  and an ``interface_reference`` pointing at the skill's native AID MQTT
  action.
- The CCI ``endpoints`` container holds, per skill, an annotated
  RelationshipElement (``this skill has this native interface``).
- The AID carries one native MQTT action per skill (the DMP v3 AID models
  ONLY the device's own communication — the caller-facing REST side is
  derived by convention, never declared).
- The AIMC carries a Variables mapping (StationState → PackMLState /
  OccupationState) plus ONE operation-delegation MappingConfiguration per CCI
  skill (source = the skill's Operation SubmodelElement, sink = the skill's
  native MQTT command affordance) with a Lua request blob.

The tests use the Python-authored Stoppering Resource factory.
"""

from __future__ import annotations

import copy
import json
import os
import sys

import pytest
from basyx.aas import model

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aas_model import build_from_model  # noqa: E402
from aas_model.resource_instances import syntegon_stoppering  # noqa: E402

def _children(el) -> list:
    """Children of a basyx Submodel / SMC (``submodel_element`` or ``value``)."""
    for attr in ("submodel_element", "value"):
        val = getattr(el, attr, None)
        if val is not None and hasattr(val, "__iter__") and not isinstance(val, (str, bytes)):
            return list(val)
    return []


def _submodel(store, id_short: str) -> model.Submodel:
    for obj in store:
        submodels = obj.submodel if hasattr(obj, "submodel") else [obj]
        for sm in submodels:
            if isinstance(sm, model.Submodel) and sm.id_short == id_short:
                return sm
    raise AssertionError(f"Submodel not found: {id_short}")


def _child(el, id_short: str):
    for c in _children(el):
        if getattr(c, "id_short", None) == id_short:
            return c
    raise AssertionError(f"Child {id_short!r} not found in {getattr(el, 'id_short', '?')}")


def _key_values(ref) -> list[str]:
    return [k.value for k in ref.key]


@pytest.fixture(scope="module")
def store():
    return build_from_model(syntegon_stoppering())


def test_registration_does_not_synthesize_missing_invocation_qualifier():
    from aas_model import Resource

    data = json.loads(syntegon_stoppering().model_dump_json())
    halt_data = data["control_component_instance"]["Skills"]["Skill"]["Halt"]["operation"]
    halt_data["qualifiers"] = [
        q for q in halt_data["qualifiers"] if q["type_"] != "invocationDelegation"
    ]
    asset = Resource.model_validate(data)
    assert not any(
        q.type_ == "invocationDelegation"
        for q in asset.control_component_instance.Skills.Skill["Halt"].operation.qualifiers
    )


def test_registration_preserves_concrete_invocation_url():
    from src.config_parser import parse_config_data

    data = json.loads(syntegon_stoppering().model_dump_json())
    original = copy.deepcopy(data)
    url = data["control_component_instance"]["Skills"]["Skill"]["Halt"]["operation"]["qualifiers"][0]["value"]
    asset = parse_config_data(data)
    halt = asset.control_component_instance.Skills.Skill["Halt"]
    deleg = next(q for q in halt.operation.qualifiers if q.type_ == "invocationDelegation")
    assert deleg.value == url
    assert data == original


def test_registration_preserves_authored_invocation_url_string():
    from src.config_parser import parse_config_data

    data = json.loads(syntegon_stoppering().model_dump_json())
    data["control_component_instance"]["Skills"]["Skill"]["Halt"]["operation"]["qualifiers"][0]["value"] = (
        "https://example.invalid/custom/halt"
    )
    asset = parse_config_data(data)
    deleg = next(
        q for q in asset.control_component_instance.Skills.Skill["Halt"].operation.qualifiers
        if q.type_ == "invocationDelegation"
    )
    assert deleg.value == "https://example.invalid/custom/halt"


def test_registration_preserves_explicitly_empty_qualifiers():
    from src.config_parser import parse_config_data

    data = json.loads(syntegon_stoppering().model_dump_json())
    data["control_component_instance"]["Skills"]["Skill"]["Halt"]["operation"]["qualifiers"] = []
    asset = parse_config_data(data)
    assert asset.control_component_instance.Skills.Skill["Halt"].operation.qualifiers == []


def test_registration_rejects_malformed_field_types_and_unknown_fields():
    from pydantic import ValidationError
    from src.config_parser import parse_config_data

    data = json.loads(syntegon_stoppering().model_dump_json())
    data["control_component_instance"]["Skills"]["Skill"]["Halt"]["operation"]["qualifiers"][0]["value"] = 42
    with pytest.raises(ValidationError):
        parse_config_data(data)

    data = json.loads(syntegon_stoppering().model_dump_json())
    data["unexpected_field"] = True
    with pytest.raises(ValidationError):
        parse_config_data(data)


def test_registration_rejects_retired_delegation_config():
    from src.config_parser import parse_config_data

    data = json.loads(syntegon_stoppering().model_dump_json())
    data["delegation_base"] = "http://old-host:8080"
    with pytest.raises(ValueError, match="delegation_base"):
        parse_config_data(data)


def test_cci_skills_have_operations_with_delegation_and_native_interface_ref(store):
    cci = _submodel(store, "ControlComponentInstance")
    skills = _child(cci, "Skills")

    skill_names = {c.id_short for c in _children(skills)}
    # Default skills + (for syntegonStoppering) the station skill.
    assert {"Halt", "Occupy", "Release"} <= skill_names

    for skill_el in _children(skills):
        name = skill_el.id_short

        # interface_reference → native MQTT action in the AID (≥5 keys,
        # last key == the skill name — the shape BT_Controller expects).
        iref = _child(skill_el, "interface_reference")
        assert isinstance(iref, model.ReferenceElement)
        keys = _key_values(iref.value)
        assert keys[0].endswith("/submodels/AssetInterfacesDescription")
        assert "interface_mqtt" in keys
        assert "InteractionMetadata" in keys
        assert keys[-1] == name

        # operation → invocationDelegation qualifier (plain delegation URL per
        # the current BaSyx wiki example; the DMP host derives from the asset
        # the fixed shared invocation service and exact owner id_short).
        op = _child(skill_el, "operation")
        assert isinstance(op, model.Operation)
        qualifier_types = {q.type for q in op.qualifier}
        assert "invocationDelegation" in qualifier_types
        deleg = next(q for q in op.qualifier if q.type == "invocationDelegation")
        assert deleg.value == f"http://dmp:8080/operations/syntegonStopperingSystemAAS/{name}"

        # Operation variables keep their meaningful names so the AAS Web GUI
        # can render + manually invoke the operation (Uuid inout; State output).
        # Outcome (the FOND branch discriminator) is NOT a default output —
        # registration-style skills (Halt/Occupy/Release) answer State only;
        # FOND-capable process skills declare it explicitly in their configs.
        assert {v.id_short for v in op.in_output_variable} == {"Uuid"}
        if name in ("Halt", "Occupy", "Release"):
            assert {v.id_short for v in op.output_variable} == {"State"}


def test_cci_endpoints_hold_skill_native_interface_relationships(store):
    cci = _submodel(store, "ControlComponentInstance")
    endpoints = _child(cci, "Endpoints")

    rels = [c for c in _children(endpoints) if isinstance(c, model.RelationshipElement)]
    assert rels, "endpoints must hold per-skill RelationshipElements"
    assert {r.id_short for r in rels} >= {"Halt", "Occupy", "Release"}

    for rel in rels:
        # first = this skill SMC in the CCI, second = its native AID action.
        first_keys = _key_values(rel.first)
        second_keys = _key_values(rel.second)
        assert first_keys[0].endswith("/submodels/ControlComponentInstance")
        assert first_keys[-1] == rel.id_short
        assert second_keys[0].endswith("/submodels/AssetInterfacesDescription")
        assert second_keys[-1] == rel.id_short


def test_aid_has_no_caller_facing_rest_interface(store):
    """DMP v3: the AID models only the device's own communication — the
    caller-facing REST surface is DERIVED by the DMP, never declared here."""
    aid = _submodel(store, "AssetInterfacesDescription")
    children = [c.id_short for c in _children(aid)]
    assert "interface_rest" not in children


def test_aid_mqtt_actions_declare_response_topics(store):
    """Every delegated skill's command affordance declares its reply topic
    (MQTT 5 request/reply: the correlated leg of the derived interaction)."""
    aid = _submodel(store, "AssetInterfacesDescription")
    mqtt = _child(aid, "interface_mqtt")
    actions = _child(_child(mqtt, "InteractionMetadata"), "actions")
    for action in _children(actions):
        forms = _child(action, "forms")
        assert _child(forms, "mqv_responseTopic").value == f"DATA/{action.id_short}"


def test_registration_preserves_authored_mqtt_terms_without_enrichment():
    from src.config_parser import parse_config_data

    data = json.loads(syntegon_stoppering().model_dump_json())
    original = copy.deepcopy(data)
    aid = parse_config_data(data).asset_interfaces_description
    assert data == original
    mqtt = aid.InterfaceTemplateForMQTT["interface_mqtt"].InteractionMetadata
    authored_actions = data["asset_interfaces_description"]["InterfaceTemplateForMQTT"]["interface_mqtt"]["InteractionMetadata"]["actions"]["property_name"]
    assert set(mqtt.actions.property_name) == set(authored_actions)
    for name, action in mqtt.actions.property_name.items():
        assert action.forms.mqv_responseTopic.value == f"DATA/{name}"
        assert authored_actions[name]["forms"]["mqv_responseTopic"]["value"] == action.forms.mqv_responseTopic.value
        assert action.forms.op is None, name  # not added: WoT defaults it to invokeaction
    authored_properties = data["asset_interfaces_description"]["InterfaceTemplateForMQTT"]["interface_mqtt"]["InteractionMetadata"]["properties"]["property_name"]
    assert set(mqtt.properties.property_name) == set(authored_properties)
    for name, prop in mqtt.properties.property_name.items():
        assert prop.forms.model_dump() == authored_properties[name]["forms"], name


def _aimc_mapping_list(store):
    """The AIMC ``MappingConfigurations`` SML (id_short may be the field-name
    snake_case ``mapping_configurations`` or the IDTA ``MappingConfigurations``)."""
    aimc = _submodel(store, "AssetInterfacesMappingConfiguration")
    for c in _children(aimc):
        if getattr(c, "id_short", "").replace("_", "").lower() == "mappingconfigurations":
            return c
    raise AssertionError("MappingConfigurations SML not found in AIMC")


def _mapping_name(mc) -> str:
    """The name of an AIMC MappingConfiguration SML item: list items carry no
    idShort (AASd-120), their name is their display name."""
    return mc.display_name.get("en")


def test_aimc_covers_variables_and_every_skill(store):
    # The station state is written into its series in Variables.
    mapping_list = _aimc_mapping_list(store)
    mappings = list(_children(mapping_list))
    assert mappings

    [state] = [mc for mc in mappings if _mapping_name(mc) == "StationState"]
    [sink] = _children(_child(state, "Sinks"))
    assert _child(sink, "SinkId").value == "Live"
    assert [key.value for key in _child(sink, "Sink").value.key[1:]] == ["State", "Station", "Segments", "Live"]

    # Every CCI skill is covered by ONE operation-delegation MappingConfiguration
    # (DMP v3 one-MC authoring: source = the skill's Operation element).
    cci = _submodel(store, "ControlComponentInstance")
    skills = _child(cci, "Skills")
    skill_names = {c.id_short for c in _children(skills)}
    mapping_names = [_mapping_name(m) for m in mappings]
    for name in skill_names:
        assert mapping_names.count(name) == 1, f"skill {name} needs its operation mapping"

    # Each mapping has a Lua transformation referencing its source.
    for mc in mappings:
        transformation = _child(mc, "Transformation")
        assert isinstance(transformation, model.Blob)
        lua = bytes(transformation.value).decode("utf-8")
        assert "aimc_main" in lua
        assert "sources." in lua

def _reference_keys(ref) -> list[str]:
    """Key TYPE + value path of a reference (value pairs as ``type:value``)."""
    return [f"{k.type}:{k.value}" for k in ref.key]


def test_aimc_skill_operation_mappings_are_one_mc(store):
    """Each skill's operation mapping: SOURCE = the skill's Operation
    SubmodelElement in the CCI (Operation key type), SINK = the skill's native
    MQTT command affordance. No caller-facing REST references exist anywhere
    (DMP v3: the REST surface is derived, never declared)."""
    mapping_list = _aimc_mapping_list(store)

    directions = {}  # skill -> set of direction tuples
    for mc in list(_children(mapping_list)):
        sources = _children(_child(mc, "Sources"))
        sinks = _children(_child(mc, "Sinks"))
        src = _child(sources[0], "Source").value
        keys = list(src.key)
        if keys[-1].type != model.KeyTypes.OPERATION:
            # non-operation mappings (the Variables mapping over the
            # StationState affordance and the OPC UA measurement data mappings)
            # source a device/AAS
            # affordance, never a CCI Operation — not part of this check
            continue
        snk = _key_values(_child(sinks[0], "Sink").value)
        skill = keys[-2].value
        directions.setdefault(skill, set()).add((
            "Skills" in _key_values(src),
            keys[-1].value,
            "interface_mqtt" in snk,
            snk[-1] == skill,
        ))

    cci = _submodel(store, "ControlComponentInstance")
    skills = _child(cci, "Skills")
    skill_names = {c.id_short for c in _children(skills)}
    assert skill_names <= set(directions)

    for name, dirs in directions.items():
        # one-MC operation authoring: CCI Operation source → native MQTT sink
        assert (True, "operation", True, True) in dirs, \
            f"{name}: expected one-MC operation mapping"

    # The operation source key carries the Operation KEY TYPE — the exact
    # signal the management node classifies the mapping as an interaction from.
    # Dual-binding legs (the OPC UA mapping of the same CCI operation) name
    # themselves after the skill too ({skill}Opcua) — the derived REST surface
    # stays disambiguated by the management node, not by the reference.
    for mc in list(_children(mapping_list)):
        sources = _children(_child(mc, "Sources"))
        src = _child(sources[0], "Source").value
        keys = list(src.key)
        if keys[-1].value != "operation":
            continue
        assert keys[-1].type == model.KeyTypes.OPERATION
        name = _mapping_name(mc)
        assert keys[-2].value == name or name.startswith(keys[-2].value), \
            f"{name}: owning skill {keys[-2].value!r} must name the mapping"

    # Each mapping carries its Lua request blob.
    for mc in list(_children(mapping_list)):
        transformation = _child(mc, "Transformation")
        assert isinstance(transformation, model.Blob)
        lua = bytes(transformation.value).decode("utf-8")
        assert "aimc_main" in lua
        assert "sources." in lua
