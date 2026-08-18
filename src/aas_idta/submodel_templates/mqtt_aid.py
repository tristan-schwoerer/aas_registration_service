"""
MQTT-extended AssetInterfacesDescription — inherits from generated IDTA AID.

Named-field style: containers hold their child elements as DIRECT named
fields (field name == id_short) — no ``value``/``submodel_element`` wrapper.
The generated AID containers (``forms``, ``property_name``, ``properties``,
``actions``, ``InteractionMetadata``, ``InterfaceTemplateForMQTT``) are
subclassed to add the MQTT-specific children:

    class MqttForm(forms):
        op: Property = Property(...)            # added on top of the base's
        mqv_retain: Property = Property(...)    # href/content_type/security

Dynamic name-keyed maps (MQTT actions/properties keyed by action/property
name) stay ``Dict[str, Item]`` fields directly on the container.
"""

from __future__ import annotations

from typing import Dict, Optional

from aas_pydantic import (
    SubmodelElementCollection, Property,
)

from aas_pydantic.submodel_templates.asset_interfaces_description import (
    forms as _BaseForm,
    property_name as _BaseProperty,
    property_name_json_schema as _BaseDataSchema,
    actions as _BaseActions,
    properties as _BaseProperties,
    InteractionMetadata as _BaseInteractionMetadata,
    InterfaceTemplateForMQTT as _BaseMqttInterface,
    AssetInterfacesDescription as _BaseAID,
    # Required (One) children of the generated classes — provided here so the
    # MQTT variants construct: forms need href/security; the interface needs
    # title + endpoint metadata.
    Title, Base, ContentType, EndpointMetadata, Href,
    security as _Security, security_t, securityDefinitions,
)

from ..constants import (
    AID_MQTT_RESPONSE_FORM, AID_MQTT_RETAIN, AID_MQTT_CONTROL_PACKET,
    AID_MQTT_QOS, AID_SYNCHRONOUS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Delta — MQTT-specific form fields
# ═══════════════════════════════════════════════════════════════════════════════

class MqttResponseForm(SubmodelElementCollection):
    """MQTT response topic form (publish topic for async operation results)."""
    semantic_id: str = AID_MQTT_RESPONSE_FORM

    href: Property = Property(
        semantic_id="https://www.w3.org/2019/wot/hypermedia#hasTarget")
    content_type: Property = Property(
        semantic_id="https://www.w3.org/2019/wot/hypermedia#forContentType")
    mqv_retain: Property = Property(
        semantic_id=AID_MQTT_RETAIN)
    mqv_control_packet: Property = Property(
        semantic_id=AID_MQTT_CONTROL_PACKET)


class MqttForm(_BaseForm):
    """Standard W3C WoT form + MQTT transport qualifiers."""
    href: Href = Href()
    security: security_t = security_t()
    op: Property = Property(
        semantic_id="https://www.w3.org/2019/wot/td#hasOperationType")
    mqv_retain: Property = Property(
        semantic_id=AID_MQTT_RETAIN)
    mqv_qos: Property = Property(
        semantic_id=AID_MQTT_QOS)
    mqv_control_packet: Property = Property(
        semantic_id=AID_MQTT_CONTROL_PACKET)
    response: MqttResponseForm = MqttResponseForm()


# ═══════════════════════════════════════════════════════════════════════════════
# Delta — WoT input/output DataSchemas on actions (and the payload DataSchema
# on properties).  The JSON Schema URL rides as a supplemental semantic id on
# the DataSchema it represents — NOT as a separate URL Property child.
# ═══════════════════════════════════════════════════════════════════════════════

# WoT Thing Description 2.0 ``ActionAffordance.input`` / ``.output`` vocabulary
# (w3.org — kept inline per the constants policy).  Both are DataSchemas, the
# same JSON-schema-derived structure the properties embed.
AID_ACTION_INPUT = "https://www.w3.org/2019/wot/td#hasInput"
AID_ACTION_OUTPUT = "https://www.w3.org/2019/wot/td#hasOutput"


class MqttActionInput(_BaseDataSchema):
    """WoT ``input`` DataSchema of an action (td#hasInput) — the command's
    JSON Schema structure (type / properties / items / enum / ranges), built
    via :func:`aas_idta.json_schema_aid.datapoint_from_schema`."""
    semantic_id: str = AID_ACTION_INPUT
    description: str = "Data schema describing the input of the action."


class MqttActionOutput(_BaseDataSchema):
    """WoT ``output`` DataSchema of an action (td#hasOutput) — the response's
    JSON Schema structure, built via ``datapoint_from_schema``."""
    semantic_id: str = AID_ACTION_OUTPUT
    description: str = "Data schema describing the output of the action."


class MqttAction(_BaseProperty):
    """Standard WoT PropertyDefinition + input/output DataSchemas (each schema
    URL rides as a supplemental semantic id on the DataSchema it represents)
    + MQTT form."""
    synchronous: Property = Property(semantic_id=AID_SYNCHRONOUS)
    input: Optional[MqttActionInput] = None
    output: Optional[MqttActionOutput] = None
    forms: MqttForm = MqttForm()


class MqttProperty(_BaseProperty):
    """Standard WoT PropertyDefinition + MQTT form.  The payload schema URL
    rides as a supplemental semantic id on the property itself."""
    forms: MqttForm = MqttForm()


# ═══════════════════════════════════════════════════════════════════════════════
# Delta — action/property containers (dynamic maps: name → Item)
# ═══════════════════════════════════════════════════════════════════════════════

class MqttActions(_BaseActions):
    """Dynamic map of MQTT actions (name → MqttAction)."""
    property_name: Dict[str, MqttAction] = {}


class MqttProperties(_BaseProperties):
    """Dynamic map of MQTT properties (name → MqttProperty)."""
    property_name: Dict[str, MqttProperty] = {}


class MqttInteractionMetadata(_BaseInteractionMetadata):
    """Interaction metadata with MQTT-specialised actions/properties."""
    actions: MqttActions = MqttActions()
    properties: MqttProperties = MqttProperties()


class MqttInterface(_BaseMqttInterface):
    """MQTT interface with extended interaction metadata."""
    title: Title = Title()
    endpoint_metadata: EndpointMetadata = EndpointMetadata(
        base=Base(),
        content_type=ContentType(),
        security=security_t(),
        security_definitions=securityDefinitions(),
    )
    interaction_metadata: MqttInteractionMetadata = MqttInteractionMetadata()


# ═══════════════════════════════════════════════════════════════════════════════
# Top-level AID submodel
# ═══════════════════════════════════════════════════════════════════════════════

class MqttAssetInterfacesDescription(_BaseAID):
    """MQTT-extended Asset Interfaces Description."""
    interface_mqtt: MqttInterface = MqttInterface()
