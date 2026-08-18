"""AAS templates — top-level Pydantic models for complete AAS types.

Partially-filled submodels (station-agnostic defaults) live in sibling
modules: ``nameplate``, ``asset_interfaces_description``,
``control_component_instance``, ``variables``, ``parameters``.  Each uses
either our modified ``submodel_templates`` or the generated aas_pydantic
fork templates as its base.
"""

from .asset import ResourceTypeAAS
from .nameplate import nameplate
from .asset_interfaces_description import (
    asset_interfaces_description, mqtt_action, mqtt_property,
)
from .control_component_instance import (
    ResourceControlComponentInstance, control_component_instance, extended_skill,
)
from .variables import variables, variable
from .parameters import Position, ResourceParameters, resource_parameters

__all__ = [
    "ResourceTypeAAS",
    "nameplate",
    "asset_interfaces_description",
    "mqtt_action",
    "mqtt_property",
    "ResourceControlComponentInstance",
    "control_component_instance",
    "extended_skill",
    "variables",
    "variable",
    "Position",
    "ResourceParameters",
    "resource_parameters",
]
