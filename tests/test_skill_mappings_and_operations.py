"""Skill operations + AIMC skill mappings — templates flow tests.

Verifies the operation-delegation wiring added to the Resource AAS:

- CCI skills carry an ``operation`` (AAS Operation) with an
  ``invocationDelegation`` qualifier pointing at the generated REST endpoint,
  and an ``interface_reference`` pointing at the skill's native AID MQTT
  action.
- The CCI ``endpoints`` container holds, per skill, an annotated
  RelationshipElement (``this skill has this native interface``).
- The AID carries an ``interface_rest`` (operation-delegation) with one action
  per skill.
- The AIMC carries a Variables mapping (StationState → PackMLState /
  OccupationState) plus one skill MappingConfiguration per CCI skill
  (native MQTT action → REST action) with a Lua transformation.

The tests use the AP2030-UNS resource config (see ``CONFIG_PATH``); override
with ``AAS_TEST_CONFIG``, or they are skipped.
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
    return build_from_json(CONFIG_PATH)


def test_delegation_base_derives_from_asset_id_short():
    """Without a ``delegation_base`` config key, the DMP host is derived from
    the asset id_short (unique per asset) as ``dmp-<id_short>`` lowercased —
    the K8s Service name convention."""
    import json

    with open(CONFIG_PATH) as f:
        data = json.load(f)
    data.pop("delegation_base", None)

    from src.templates.builder import build_from_dict

    cci = _submodel(build_from_dict(data), "ControlComponentInstance")
    skills = _child(cci, "Skills")
    halt = next(s for s in _children(skills) if s.id_short == "Halt")
    op = _child(halt, "operation")
    deleg = next(q for q in op.qualifier if q.type == "invocationDelegation")
    assert deleg.value.startswith("http://dmp-syntegonstopperingsystemaas:8080")
    assert deleg.value.endswith("/operations/syntegonStopperingSystemAAS/Halt")


def test_delegation_base_config_override_is_respected():
    """An explicit ``delegation_base`` config key (which may itself use the
    ``{dmp_host}`` macro) overrides the derived default."""
    import json

    with open(CONFIG_PATH) as f:
        data = json.load(f)
    data["delegation_base"] = "http://{dmp_host}.robotics.svc.cluster.local:8080"

    from src.templates.builder import build_from_dict

    cci = _submodel(build_from_dict(data), "ControlComponentInstance")
    skills = _child(cci, "Skills")
    halt = next(s for s in _children(skills) if s.id_short == "Halt")
    op = _child(halt, "operation")
    deleg = next(q for q in op.qualifier if q.type == "invocationDelegation")
    assert deleg.value.startswith(
        "http://dmp-syntegonstopperingsystemaas.robotics.svc.cluster.local:8080")


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
        # id_short, lowercased, and the real AAS id_short is substituted for
        # the macro).
        op = _child(skill_el, "operation")
        assert isinstance(op, model.Operation)
        qualifier_types = {q.type for q in op.qualifier}
        assert "invocationDelegation" in qualifier_types
        deleg = next(q for q in op.qualifier if q.type == "invocationDelegation")
        assert deleg.value.startswith("http://dmp-syntegonstopperingsystemaas:8080")
        assert deleg.value.endswith(f"/operations/syntegonStopperingSystemAAS/{name}")

        # Operation variables keep their meaningful names so the AAS Web GUI
        # can render + manually invoke the operation (Uuid inout; State/Outcome
        # output for skills with a response).
        assert {v.id_short for v in op.in_output_variable} == {"Uuid"}
        if name in ("Occupy", "Release", "Stoppering"):
            assert {v.id_short for v in op.output_variable} == {"State", "Outcome"}
        else:
            assert len(op.output_variable) == 0


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


def test_aid_has_rest_operation_delegation_interface(store):
    aid = _submodel(store, "AssetInterfacesDescription")
    rest = _child(aid, "interface_rest")

    actions = _child(_child(rest, "InteractionMetadata"), "actions")
    action_names = {a.id_short for a in _children(actions)}
    assert {"Halt", "Occupy", "Release"} <= action_names

    for action in _children(actions):
        forms = _child(action, "forms")
        href = _child(forms, "href")
        assert href.value.startswith("/operations/")
        assert href.value.endswith(f"/{action.id_short}")


def _aimc_mapping_list(store):
    """The AIMC ``MappingConfigurations`` SML (id_short may be the field-name
    snake_case ``mapping_configurations`` or the IDTA ``MappingConfigurations``)."""
    aimc = _submodel(store, "AssetInterfacesMappingConfiguration")
    for c in _children(aimc):
        if getattr(c, "id_short", "").replace("_", "").lower() == "mappingconfigurations":
            return c
    raise AssertionError("MappingConfigurations SML not found in AIMC")


def _mapping_name(mc) -> str:
    """The real id_short of an AIMC MappingConfiguration SML item.

    SML items carry their id_short in a temp Property (AASd-120 workaround);
    the actual SMC id_short is a ``generated_submodel_list_hack_`` placeholder.
    """
    for c in _children(mc):
        if isinstance(c, model.Property) and c.id_short.startswith("temp_id_short_attribute"):
            return str(c.value)
    return mc.id_short


def test_aimc_covers_variables_and_every_skill(store):
    # Variables mapping lives in MappingConfigurations.
    mapping_list = _aimc_mapping_list(store)
    mappings = list(_children(mapping_list))
    assert mappings

    sink_ids = set()
    for mc in mappings:
        sinks = _child(mc, "Sinks")
        for snk in _children(sinks):
            sink_id = _child(snk, "SinkId")
            sink_ids.add(sink_id.value)
    assert {"PackMLState", "OccupationState"} <= sink_ids

    # Every CCI skill is covered by TWO directional mappings (request +
    # response) in MappingConfigurations.
    cci = _submodel(store, "ControlComponentInstance")
    skills = _child(cci, "Skills")
    skill_names = {c.id_short for c in _children(skills)}
    mapping_names = [_mapping_name(m) for m in mappings]
    for name in skill_names:
        assert mapping_names.count(name) == 1, f"skill {name} needs a response mapping"
        assert mapping_names.count(f"{name}Request") == 1, f"skill {name} needs a request mapping"

    # Each mapping has a Lua transformation referencing its source.
    for mc in mappings:
        transformation = _child(mc, "Transformation")
        assert isinstance(transformation, model.Blob)
        lua = bytes(transformation.value).decode("utf-8")
        assert "aimc_main" in lua
        assert "sources." in lua


def test_aimc_skill_mapping_sources_sinks_reference_native_and_rest(store):
    mapping_list = _aimc_mapping_list(store)

    for mc in list(_children(mapping_list)):
        name = _mapping_name(mc)

        sources = _child(mc, "Sources")
        source_refs = []
        for src in _children(sources):
            source = _child(src, "Source")
            source_refs.append(_key_values(source.value))
        sinks = _child(mc, "Sinks")
        sink_refs = []
        for snk in _children(sinks):
            sink = _child(snk, "Sink")
            sink_refs.append(_key_values(sink.value))

        # The Variables mapping ("MQTT") points at the StationState property.
        if name == "MQTT":
            assert any("properties" in r and r[-1] == "StationState" for r in source_refs)
            continue


def test_aimc_skill_mappings_are_request_and_response_directions(store):
    """Each skill has TWO plain directional MappingConfigurations:
    request (REST action → MQTT action) and response (MQTT action → REST
    action), each with its own Lua blob."""
    mapping_list = _aimc_mapping_list(store)

    directions = {}  # skill -> set of direction tuples
    for mc in list(_children(mapping_list)):
        sources = _children(_child(mc, "Sources"))
        sinks = _children(_child(mc, "Sinks"))
        src = _key_values(_child(sources[0], "Source").value)
        snk = _key_values(_child(sinks[0], "Sink").value)
        if src[-1] == "StationState":
            continue  # the Variables mapping
        skill = src[-1]
        directions.setdefault(skill, set()).add((
            "interface_rest" in src, "interface_mqtt" in src,
            "interface_mqtt" in snk, "interface_rest" in snk,
        ))

    cci = _submodel(store, "ControlComponentInstance")
    skills = _child(cci, "Skills")
    skill_names = {c.id_short for c in _children(skills)}
    assert skill_names <= set(directions)

    for name, dirs in directions.items():
        # request: REST source → MQTT sink; response: MQTT source → REST sink
        assert (True, False, True, False) in dirs, f"{name}: missing request direction"
        assert (False, True, False, True) in dirs, f"{name}: missing response direction"

    # Each direction carries its own Lua transformation blob.
    for mc in list(_children(mapping_list)):
        sources = _children(_child(mc, "Sources"))
        src = _key_values(_child(sources[0], "Source").value)
        if src[-1] == "StationState":
            continue
        transformation = _child(mc, "Transformation")
        assert isinstance(transformation, model.Blob)
        lua = bytes(transformation.value).decode("utf-8")
        assert "aimc_main" in lua
        assert "sources." in lua


def _config_with_write_delegated_location():
    """The resource config with the ``Location`` parameter opted into property
    write-delegation via a ``writeDelegation`` qualifier."""
    import json
    with open(CONFIG_PATH) as f:
        data = json.load(f)
    data["parameters"]["parameter"]["Location"]["qualifiers"] = [
        {
            "type_": "writeDelegation",
            "value": "{delegation_base}/properties/{aas_id_short}/Location",
            "value_type": "xs:string",
            "kind": "ConceptQualifier",
        }
    ]
    return data


def test_property_write_delegation_qualifier_on_parameter():
    """A parameter carrying a ``writeDelegation`` qualifier keeps it, with the
    ``{delegation_base}``/``{aas_id_short}`` macros resolved to the resource's
    DMP base and AAS id_short."""
    from src.config_parser import parse_config_data
    asset = parse_config_data(_config_with_write_delegated_location())
    location = asset.parameters.parameter["Location"]
    quals = {q.type_: q.value for q in location.qualifiers}
    assert "writeDelegation" in quals
    assert quals["writeDelegation"] == (
        "http://dmp-syntegonstopperingsystemaas:8080/properties/syntegonStopperingSystemAAS/Location")


def test_property_write_delegation_rest_interface_and_aimc():
    """Opting a property into write-delegation auto-wires a REST write property
    (PUT, writeProperty) and an AIMC mapping configuration."""
    from src.config_parser import parse_config_data
    asset = parse_config_data(_config_with_write_delegated_location())

    # REST interface write property.
    rest = asset.asset_interfaces_description.interface_rest
    props = rest.InteractionMetadata.properties.property_name
    assert "Location" in props
    loc = props["Location"]
    assert loc.forms.href.value == "/properties/syntegonStopperingSystemAAS/Location"
    assert loc.forms.op.value == "writeProperty"
    assert loc.forms.htv_methodName.value == "PUT"

    # AIMC mapping: native MQTT action source → REST property sink.
    aimc = asset.asset_interfaces_mapping_configuration
    mc = next(
        (m for m in aimc.MappingConfigurations.value if m.id_short == "Location"),
        None,
    )
    assert mc is not None
    src_keys = mc.Sources.value[0].Source.value.key
    snk_keys = mc.Sinks.value[0].Sink.value.key
    assert src_keys[-1].value == "Location" and "actions" in [k.value for k in src_keys]
    assert snk_keys[-1].value == "Location" and "interface_rest" in [k.value for k in snk_keys]
    lua = (mc.Transformation.value.decode()
           if isinstance(mc.Transformation.value, bytes) else mc.Transformation.value)
    assert "aimc_main" in lua
