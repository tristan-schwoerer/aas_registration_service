"""JSON Schema → AID object-schema converter tests (aas_idta flow).

Verifies that a JSON Schema (draft 2020-12) can be turned into the AID
``property_name`` object-schema structure instead of hand-building it:
``type`` / ``title`` / ``description`` / ``enum`` / nested ``properties`` /
array ``items`` + ranges, with ``$ref`` + ``allOf`` dereferencing, and that
it composes with the MQTT property builder (forms + schema URL preserved).

Named-field style: datapoint children are DIRECT named fields (``dp.type``,
``dp.forms`` — no ``value`` wrapper).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "third_party", "aas_pydantic")))

from src.aas_idta.constants import SCHEMA_BASE  # noqa: E402
from src.aas_idta.json_schema_aid import (  # noqa: E402
    datapoint_from_schema,
    load_schema,
    populate_datapoint,
)
from src.aas_idta.resource_template.asset_interfaces_description import (  # noqa: E402
    asset_interfaces_description,
    mqtt_action,
    mqtt_property,
)
from src.aas_idta.submodel_templates.mqtt_aid import MqttForm, MqttProperty  # noqa: E402


def _station_state_schema():
    return load_schema(f"{SCHEMA_BASE}/stationState.schema.json")


def test_load_schema_dereferences_refs():
    """``allOf`` + ``$ref`` resolve: the base ``data.schema.json``
    (TimeStamp) is merged with the specific State/ProcessQueue."""
    flat = _station_state_schema()
    assert flat["type"] == "object"
    props = flat["properties"]
    assert set(props) == {"TimeStamp", "State", "ProcessQueue"}
    assert props["State"]["type"] == "string"
    assert len(props["State"]["enum"]) == 17
    assert props["ProcessQueue"]["type"] == "array"
    assert props["ProcessQueue"]["items"]["type"] == "string"


def test_datapoint_from_schema_builds_object_schema():
    """The AID datapoint carries the WoT object-schema structure: type,
    title, description, nested ``properties`` map, enum SML, array items."""
    dp = datapoint_from_schema(_station_state_schema(), key="StationState")
    assert dp.id_short == "StationState"
    assert dp.key.value == "StationState"
    assert dp.type.value == "object"
    assert dp.title.value == "Station response state"
    assert dp.description.startswith("JSON Schema for the status")

    nested = dp.properties.property_name
    assert set(nested) == {"TimeStamp", "State", "ProcessQueue"}
    assert nested["State"].type.value == "string"
    assert [p.value for p in nested["State"].enum.value][:3] == [
        "IDLE", "STARTING", "EXECUTE",
    ]
    assert nested["ProcessQueue"].type.value == "array"
    assert nested["ProcessQueue"].items.type.value == "string"


def test_datapoint_round_trip():
    """model_dump → model_validate preserves the nested structure."""
    dp = datapoint_from_schema(_station_state_schema(), key="StationState")
    back = type(dp).model_validate(
        json.loads(json.dumps(dp.model_dump(), default=str))
    )
    nested = back.properties.property_name
    assert set(nested) == {"TimeStamp", "State", "ProcessQueue"}
    assert [p.value for p in nested["State"].enum.value][:1] == ["IDLE"]


def test_populate_datapoint_composes_with_mqtt_property():
    """Embedding a schema into an MqttProperty leaves its forms untouched and
    records the schema URL as a supplemental semantic id on the property
    (the resource template's StationState)."""
    prop = mqtt_property("StationState", "/DATA/State", schema=_station_state_schema())
    assert isinstance(prop, MqttProperty)
    # schema URL rides as a supplemental semantic id (appended to the
    # template's own td#name default)
    assert any("stationState.schema.json" in s for s in prop.supplemental_semantic_ids)
    assert prop.forms.href.value == "/DATA/State"
    assert prop.type.value == "object"
    nested = prop.properties.property_name
    assert "ProcessQueue" in nested
    assert [p.value for p in nested["State"].enum.value][:2] == ["IDLE", "STARTING"]


def test_resource_aid_station_state_embeds_schema():
    """The Resource AID's StationState property embeds the schema structure
    while keeping its MQTT form."""
    aid = asset_interfaces_description()
    im = aid.interface_mqtt.interaction_metadata
    ss = im.properties.property_name["StationState"]
    assert ss.type.value == "object"
    assert set(ss.properties.property_name) == {
        "TimeStamp", "State", "ProcessQueue",
    }
    assert ss.forms.href.value == "/DATA/State"


def test_array_prefix_items_homogeneous_type():
    """``position.schema.json`` is an object whose ``Position`` array uses a
    homogeneous ``prefixItems`` tuple (x/y/theta all numbers) → the array's
    ``items`` type is number, bounded by minItems/maxItems."""
    flat = load_schema(f"{SCHEMA_BASE}/position.schema.json")
    dp = datapoint_from_schema(flat, key="PositionData")
    assert dp.type.value == "object"
    pos = dp.properties.property_name["Position"]
    assert pos.type.value == "array"
    assert pos.items.type.value == "number"
    assert pos.items_range.min == 2
    assert pos.items_range.max == 3


def test_move_command_allof_merges():
    """``moveCommand.json`` composes command.schema.json (Uuid) with its own
    TargetPos array via ``allOf``."""
    flat = load_schema(f"{SCHEMA_BASE}/moveCommand.json")
    assert set(flat["properties"]) == {"Uuid", "TargetPos"}
    dp = datapoint_from_schema(flat, key="moveCommand")
    nested = dp.properties.property_name
    assert nested["TargetPos"].type.value == "array"
    assert nested["TargetPos"].items.type.value == "number"
    assert nested["TargetPos"].items_range.min == 2
    assert nested["TargetPos"].items_range.max == 2


def test_datapoint_from_schema_takes_form_inputs():
    """The mandatory ``forms`` container carries the transport binding passed
    to the constructor — the bare datapoint gets a plain form with the topic;
    a ready ``MqttForm`` carries the MQTT qualifiers + WoT ``op``."""
    # 1. bare property_name: href (the topic) lands in the form
    dp = datapoint_from_schema(
        _station_state_schema(), key="StationState", href="/DATA/State"
    )
    assert type(dp.forms).__name__ == "forms"
    assert dp.forms.href.value == "/DATA/State"
    # generic forms has no ``op`` field — it is skipped, not forced
    assert "op" not in type(dp.forms).model_fields

    # 2. a ready MqttForm carries href + op + content_type (MQTT qualifiers)
    mqtt = datapoint_from_schema(
        _station_state_schema(), key="State",
        forms=MqttForm(), href="/DATA/State", op="observeProperty",
        content_type="application/json",
    )
    assert type(mqtt.forms).__name__ == "MqttForm"
    assert mqtt.forms.href.value == "/DATA/State"
    assert mqtt.forms.op.value == "observeProperty"
    assert mqtt.forms.content_type.value == "application/json"

    # 3. an already-set forms (MQTT builder) is left alone when no fields pass
    prop = mqtt_property("StationState", "/DATA/State", schema=_station_state_schema())
    assert prop.forms.href.value == "/DATA/State"
    assert prop.forms.mqv_qos.value == "0"


def test_resource_aid_actions_embed_input_output_schemas():
    """WoT TD 2.0 ``ActionAffordance.input``/``output`` are DataSchemas — the
    Resource actions embed the command/response JSON Schema structures, just
    like properties embed their payload schema.  Halt has no response, so its
    ``output`` stays absent."""
    # The standalone builder constructs both DataSchemas by default
    occupy = mqtt_action("Occupy", synchronous=True)
    assert type(occupy.input).__name__ == "MqttActionInput"
    assert type(occupy.output).__name__ == "MqttActionOutput"
    assert set(occupy.output.properties.property_name) >= {"TimeStamp", "Uuid", "State", "Outcome"}
    halt = mqtt_action("Halt", synchronous=True, has_response=False)
    assert type(halt.input).__name__ == "MqttActionInput"
    assert halt.output is None

    # The Resource AID carries them per action
    aid = asset_interfaces_description()
    actions = aid.interface_mqtt.interaction_metadata.actions.property_name

    halt = actions["Halt"]
    assert type(halt.input).__name__ == "MqttActionInput"
    assert halt.input.type.value == "object"
    # command.schema.json → { Uuid: string }
    assert set(halt.input.properties.property_name) == {"Uuid"}
    assert halt.input.properties.property_name["Uuid"].type.value == "string"
    assert halt.input.supplemental_semantic_ids[0].endswith("command.schema.json")
    # no response → no output DataSchema
    assert halt.output is None

    occupy = actions["Occupy"]
    assert type(occupy.input).__name__ == "MqttActionInput"
    assert type(occupy.output).__name__ == "MqttActionOutput"
    assert occupy.output.type.value == "object"
    assert occupy.input.supplemental_semantic_ids[0].endswith("command.schema.json")
    assert occupy.output.supplemental_semantic_ids[0].endswith("commandResponse.schema.json")
