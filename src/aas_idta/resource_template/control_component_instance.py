"""Control Component Instance partial — mandatory Resource skills + MQTT endpoint.

Built on our extended CCI (``..submodel_templates.control_component_instance``),
which extends the generated IDTA ControlComponentInstance Skill with an
interface reference to the corresponding AID action.

Named-field style: children are DIRECT named fields (no ``value``/``submodel_element``
wrapper); dynamic maps (endpoints/skills) are ``Dict[str, X]`` fields.
"""

from __future__ import annotations

from aas_pydantic import (
    ExternalReference, Key, ModelReference, ReferenceElement,
)
from aas_pydantic.submodel_templates.control_component_instance import (
    ControlComponentInstance, Endpoints, Endpoint, Type_instance,
    InterfaceReference, EndpointReference,
)

from ..constants import BROKER, SITE
from ..submodel_templates.control_component_instance import (
    ExtendedSkill, ExtendedSkills,
)
from ._helpers import put


class ResourceControlComponentInstance(ControlComponentInstance):
    """CCI variant that uses ExtendedSkills and default-constructs its
    mandatory children (endpoints / skills / type)."""
    endpoints: Endpoints = Endpoints(
        endpoint={
            "endpoint": Endpoint(
                interface_reference=InterfaceReference(
                    value=ExternalReference(key=(Key(type_="GlobalReference", value="https://admin-shell.io/idta/ControlComponent/Interface/MQTT/1/0"),))
                ),
                endpoint_reference=EndpointReference(
                    value=ExternalReference(key=(Key(type_="GlobalReference", value=f"{BROKER}/{SITE}/{{station_name}}"),))
                ),
            ),
        },
    )
    skills: ExtendedSkills = ExtendedSkills()
    type: Type_instance = Type_instance(
        value=ModelReference(
            key=(Key(type_="Submodel", value="{aas_id}/submodels/ControlComponentType"),)
        )
    )


def extended_skill(name: str, *, aas_id: str = "", disabled: bool = False) -> ExtendedSkill:
    """Build a standard ExtendedSkill for the CCI."""
    skill = ExtendedSkill()
    skill.disabled.value = str(disabled).lower()
    if aas_id:
        skill.interface_reference = ReferenceElement(
            value=ModelReference(key=(Key(type_="AssetAdministrationShell", value=aas_id),))
        )
    return skill


def control_component_instance() -> ResourceControlComponentInstance:
    """ControlComponentInstance with mandatory Resource skills + MQTT endpoint."""
    skills = ExtendedSkills()
    put(skills.skill, "Halt", extended_skill("Halt"))
    put(skills.skill, "Occupy", extended_skill("Occupy"))
    put(skills.skill, "Release", extended_skill("Release"))
    return ResourceControlComponentInstance(
        id_short="ControlComponentInstance",
        skills=skills,
    )
