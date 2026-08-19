"""AIMC partial — mandatory Resource live-data mappings (PackMLState, OccupationState).

Maps the Resource's mandatory variables to the AID ``StationState`` property
source via the IDTA AIMC 2.0 MappingConfiguration.  The Lua ``transformation``
expresses which JSON field of the source payload feeds each sink:

    sources.StationState.State         → PackMLState
    sources.StationState.ProcessQueue  → OccupationState

All references use the ``{aas_id}`` macro (resolved by id_injector), so the
AIMC always points at this AAS's own AID/Variables submodels.

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

# ── Reference paths (self-referential — {aas_id} resolved by id_injector) ──
AID_REF = "{aas_id}/submodels/AssetInterfacesDescription"
VARIABLES_REF = "{aas_id}/submodels/Variables"

AID_PROPERTY_PATH = (
    Key(type_="Submodel", value=AID_REF),
    Key(type_="SubmodelElementCollection", value="interface_mqtt"),
    Key(type_="SubmodelElementCollection", value="interaction_metadata"),
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


def source(name: str, ref: ModelReference) -> Source:
    """A single AID source: the property reference + a stable source id."""
    return Source(
        id_short=name,
        source=Source_source(value=ref),
        source_id=SourceId(value=name),
    )


def sink(name: str, ref: ModelReference) -> Sink:
    """A single sink: the submodel element reference + a stable sink id."""
    return Sink(
        id_short=name,
        sink=Sink_sink(value=ref),
        sink_id=SinkId(value=name),
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
        default_polling_interval=DefaultPollingInterval(value="0.0"),
        transformation=Transformation(value=transformation),
        sources=Sources(value=sources),
        sinks=Sinks(value=sinks),
    )


_DEFAULT_TRANSFORMATION = """\
function aimc_main(sources)
    return {
        PackMLState     = sources.StationState.State,
        OccupationState = sources.StationState.ProcessQueue,
    }
end
"""


def asset_interfaces_mapping_configuration() -> Aimc:
    """AIMC submodel with the mandatory Resource live-data mappings.

    PackMLState and OccupationState both read from the AID ``StationState``
    property (``/DATA/State``); the Lua transformation picks the JSON field
    of the payload each variable maps to.
    """
    mc = mapping_configuration(
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
    return Aimc(
        id_short="AssetInterfacesMappingConfiguration",
        mapping_configurations=AimcMappingConfigurations(value=[mc]),
    )
