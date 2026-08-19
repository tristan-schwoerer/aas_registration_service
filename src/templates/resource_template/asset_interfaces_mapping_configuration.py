"""AIMC partial — mandatory Resource live-data mappings (Variables + Skills).

Maps the Resource's mandatory variables AND skills via IDTA AIMC 2.0
MappingConfigurations:

- **Variables** — ``PackMLState``/``OccupationState`` read from the AID
  ``StationState`` property (``/DATA/State``); the Lua ``transformation``
  picks the JSON field of the payload each variable maps to:

      sources.StationState.State         → PackMLState
      sources.StationState.ProcessQueue  → OccupationState

- **Skills** — each skill maps its NATIVE MQTT action (``interface_mqtt``)
  to its generated REST operation-delegation action (``interface_rest``,
  described in ``rest_aid``); the Lua transformation converts between the
  REST call and the MQTT command/response payloads.

All references use the ``{aas_id}`` / ``{aas_id_short}`` macros (resolved by
id_injector), so the AIMC always points at this AAS's own submodels.

Named-field style: children are DIRECT named fields on the container (no
``value``/``submodel_element`` wrapper).
"""

from __future__ import annotations

from aas_pydantic import (
    Key, ModelReference, ReferenceElement,
)
from aas_pydantic.submodel_templates.asset_interfaces_mapping_configuration import (
    Source, Sink, Sources, Sinks,
    Source_source, Sink_sink,
    DefaultPollingInterval, SourceId, SinkId,
)

from ..submodel_templates.aimc import (
    Aimc, AimcMappingConfiguration, AimcMappingConfigurations,
    Transformation,
)
from ._helpers import DEFAULT_SKILLS

# ── Reference paths (self-referential — {aas_id} resolved by id_injector) ──
AID_REF = "{aas_id}/submodels/AssetInterfacesDescription"
VARIABLES_REF = "{aas_id}/submodels/Variables"

AID_PROPERTY_PATH = (
    Key(type_="Submodel", value=AID_REF),
    Key(type_="SubmodelElementCollection", value="interface_mqtt"),
    Key(type_="SubmodelElementCollection", value="InteractionMetadata"),
    Key(type_="SubmodelElementCollection", value="properties"),
)

AID_MQTT_ACTION_PATH = (
    Key(type_="Submodel", value=AID_REF),
    Key(type_="SubmodelElementCollection", value="interface_mqtt"),
    Key(type_="SubmodelElementCollection", value="InteractionMetadata"),
    Key(type_="SubmodelElementCollection", value="actions"),
)

AID_REST_ACTION_PATH = (
    Key(type_="Submodel", value=AID_REF),
    Key(type_="SubmodelElementCollection", value="interface_rest"),
    Key(type_="SubmodelElementCollection", value="InteractionMetadata"),
    Key(type_="SubmodelElementCollection", value="actions"),
)

AID_REST_PROPERTY_PATH = (
    Key(type_="Submodel", value=AID_REF),
    Key(type_="SubmodelElementCollection", value="interface_rest"),
    Key(type_="SubmodelElementCollection", value="InteractionMetadata"),
    Key(type_="SubmodelElementCollection", value="properties"),
)

VARIABLE_PATH = (
    Key(type_="Submodel", value=VARIABLES_REF),
)


def _property_ref(property_name: str) -> ModelReference:
    """Reference to an AID property (source) — e.g. .../properties/StationState."""
    return ModelReference(key=AID_PROPERTY_PATH + (Key(type_="SubmodelElementCollection", value=property_name),))


def _variable_ref(variable_name: str) -> ModelReference:
    """Reference to a Variables submodel element (sink) — e.g. .../Variables/PackMLState."""
    return ModelReference(key=VARIABLE_PATH + (Key(type_="SubmodelElementCollection", value=variable_name),))


def _mqtt_action_ref(name: str) -> ModelReference:
    """Reference to a skill's native MQTT action (interface_mqtt)."""
    return ModelReference(key=AID_MQTT_ACTION_PATH + (Key(type_="SubmodelElementCollection", value=name),))


def _rest_action_ref(name: str) -> ModelReference:
    """Reference to a skill's REST operation-delegation action (interface_rest)."""
    return ModelReference(key=AID_REST_ACTION_PATH + (Key(type_="SubmodelElementCollection", value=name),))


def _rest_property_ref(name: str) -> ModelReference:
    """Reference to a property's REST write-delegation endpoint (interface_rest)."""
    return ModelReference(key=AID_REST_PROPERTY_PATH + (Key(type_="SubmodelElementCollection", value=name),))


def source(name: str, ref: ModelReference) -> Source:
    """A single AID source: the affordance reference + a stable source id."""
    return Source(
        id_short=name,
        Source=Source_source(value=ref),
        SourceId=SourceId(value=name),
    )


def sink(name: str, ref: ModelReference) -> Sink:
    """A single sink: the submodel element reference + a stable sink id."""
    return Sink(
        id_short=name,
        Sink=Sink_sink(value=ref),
        SinkId=SinkId(value=name),
    )


def mapping_configuration(
    *,
    id_short: str,
    sources: list[Source],
    sinks: list[Sink],
    transformation: str,
) -> AimcMappingConfiguration:
    """One MappingConfiguration: AID sources, AAS sinks and the Lua mapping."""
    return AimcMappingConfiguration(
        id_short=id_short,
        DefaultPollingInterval=DefaultPollingInterval(value="0.0"),
        Transformation=Transformation(value=transformation),
        Sources=Sources(value=sources),
        Sinks=Sinks(value=sinks),
    )


_DEFAULT_TRANSFORMATION = """\
function aimc_main(sources)
    return {
        PackMLState     = sources.StationState.State,
        OccupationState = sources.StationState.ProcessQueue,
    }
end
"""


def _skill_transformation(name: str) -> str:
    """Lua converting between the skill's REST operation-delegation call and
    its native MQTT action (request: REST → MQTT, response: MQTT → REST).

    Both payloads carry the command / commandResponse fields, so the mapping
    is a field passthrough; the request direction is documented in the
    script (a DMP packs the operation variables into the command message).
    """
    return f"""\
-- Skill '{name}': operation-delegation REST endpoint <-> native MQTT action.
-- Request  (REST -> MQTT): the DMP packs the AAS OperationVariables into the
--   native command message:
--     command = {{ Uuid = rest.Uuid }}
-- Response (MQTT -> REST): aimc_main rebuilds the OperationVariables from
--   the native MQTT response payload (/DATA/{name}):
function aimc_main(sources)
    local mqtt = sources.{name}
    return {{
        {name} = {{
            Uuid    = mqtt.Uuid,
            State   = mqtt.State,
            Outcome = mqtt.Outcome,
        }},
    }}
end
"""


def variables_mapping_configuration() -> AimcMappingConfiguration:
    """The mandatory Variables mapping: StationState property → PackMLState /
    OccupationState."""
    return mapping_configuration(
        id_short="MQTT",
        sources=[
            source("StationState", _property_ref("StationState")),
        ],
        sinks=[
            sink("PackMLState", _variable_ref("PackMLState")),
            sink("OccupationState", _variable_ref("OccupationState")),
        ],
        transformation=_DEFAULT_TRANSFORMATION,
    )


def skill_mapping_configuration(name: str) -> AimcMappingConfiguration:
    """One skill MappingConfiguration: native MQTT action → REST
    operation-delegation action, with the REST↔MQTT Lua transformation."""
    return mapping_configuration(
        id_short=name,
        sources=[
            source(name, _mqtt_action_ref(name)),
        ],
        sinks=[
            sink(name, _rest_action_ref(name)),
        ],
        transformation=_skill_transformation(name),
    )


def _property_write_transformation(name: str) -> str:
    """Lua converting between a property's REST write-delegation endpoint and
    its native MQTT action (write: REST → MQTT; acknowledgement: MQTT → REST)."""
    return f"""\
-- Property '{name}': REST write-delegation endpoint <-> native MQTT action.
-- Write (REST -> MQTT): the DMP packs the written value into the native
--   command message, e.g.:
--     command = {{ Uuid = <correlation>, {name} = rest.{name} }}
-- Ack   (MQTT -> REST): aimc_main maps the MQTT response/ack to the REST
--   write response:
function aimc_main(sources)
    local mqtt = sources.{name}
    return {{
        {name} = {{
            Value   = mqtt.{name},
            State   = mqtt.State,
        }},
    }}
end
"""


def property_mapping_configuration(name: str) -> AimcMappingConfiguration:
    """One property-write MappingConfiguration: native MQTT action → REST
    write-delegation property, with the write↔ack Lua transformation."""
    return mapping_configuration(
        id_short=name,
        sources=[
            source(name, _mqtt_action_ref(name)),
        ],
        sinks=[
            sink(name, _rest_property_ref(name)),
        ],
        transformation=_property_write_transformation(name),
    )


def asset_interfaces_mapping_configuration() -> Aimc:
    """AIMC submodel with the mandatory Resource mappings.

    The Variables mapping (PackMLState/OccupationState ← StationState) plus
    one MappingConfiguration per default skill (native MQTT action → REST
    operation-delegation action).  Resource configs add their own skill
    mappings under ``mapping_configurations``.
    """
    mcs = [variables_mapping_configuration()]
    for name, _synchronous, _has_response in DEFAULT_SKILLS:
        mcs.append(skill_mapping_configuration(name))
    return Aimc(
        id_short="AssetInterfacesMappingConfiguration",
        MappingConfigurations=AimcMappingConfigurations(value=mcs),
    )
