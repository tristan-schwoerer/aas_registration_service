#!/usr/bin/env python3
"""
Example: Build a compliant AAS using generated IDTA templates.

Key design: every leaf AAS element (Property, ReferenceElement, etc.) is a
proper Pydantic model with pre-filled semantic_id, description, and qualifiers.
You only set the runtime *value* — metadata flows from the template default.

Named-field style: containers hold their children as DIRECT named fields
(no ``value``/``submodel_element`` wrapper); multi-cardinality children are
``Dict[str, X]`` maps keyed by id_short.

Usage:
    cd Registration_Service
    python scripts/example_idta_compliant_aas.py
"""

import os
import sys
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "third_party", "aas_pydantic"))

from aas_pydantic.submodel_templates.nameplate import (
    Nameplate, URIOfTheProduct, ManufacturerName, ManufacturerProductDesignation,
    AddressInformation, Street, Zipcode, CityTown, NationalCode,
    OrderCodeOfManufacturer,
    SerialNumber, YearOfConstruction, ManufacturerProductType, CountryOfOrigin,
    AssetSpecificProperties, ArbitraryProperty,
)
from aas_pydantic.submodel_templates.capability_description import (
    CapabilityDescription,
    CapabilityContainer,
    CapabilitySet,
    CapabilityComment,
    CapabilityRelations,
    CapabilityRealizedBy,
)
# The resource-level CCI extension lives in the ``src`` package; the package
# layout treats ``src`` as the top-level package (relative imports resolve
# within it), so add the repo root to sys.path.
sys.path.insert(0, os.path.join(_HERE, ".."))

from src.templates.submodel_templates.control_component_instance import ExtendedSkill
from aas_pydantic.submodel_templates.control_component_instance import (
    ControlComponentInstance,
    Endpoint,
    Endpoints,
    InterfaceReference,
    EndpointReference,
    Type_instance,
    Skills,
)
from aas_pydantic import (
    Capability,
    ExternalReference,
    Key,
    ModelReference,
    convert_model_to_submodel,
)

BASE_URL = "https://smartproductionlab.aau.dk"
ASSET_ID = "syntegonStopperingSystemAAS"


def sm_id(name: str) -> str:
    return f"{BASE_URL}/submodels/instances/{ASSET_ID}/{name}"


# ═══════════════════════════════════════════════════════════════════════
# Pattern 1: Mutate after construction
#   Accept all template defaults (metadata is pre-filled), then set
#   only the runtime values on the leaf models.  Children are DIRECT named
#   fields; multi-cardinality maps are keyed by id_short.
# ═══════════════════════════════════════════════════════════════════════

# ── Nameplate ──
# Mandatory (One) children are provided at construction — metadata flows from
# the template defaults, only runtime values are set here.
nameplate = Nameplate(
    id_short="Nameplate",
    id=sm_id("Nameplate"),
    u_r_i_of_the_product=URIOfTheProduct(
        value="https://example.com/products/SYN-SS-001"),
    manufacturer_name=ManufacturerName(value={"en": "Syntegon Technology GmbH"}),
    manufacturer_product_designation=ManufacturerProductDesignation(
        value={"en": "Stoppering System 2024"}),
    address_information=AddressInformation(
        street=Street(value={"en": "Nybrovej 114"}),
        zipcode=Zipcode(value={"en": "9220"}),
        city_town=CityTown(value={"en": "Aalborg Øst"}),
        national_code=NationalCode(value={"en": "DK"}),
    ),
    order_code_of_manufacturer=OrderCodeOfManufacturer(value="SYN-SS-2024-001"),
)
# Optional children — metadata already on the Property defaults
nameplate.serial_number = SerialNumber(value="SYN-SS-2024-001")
nameplate.year_of_construction = YearOfConstruction(value="2024")
nameplate.manufacturer_product_type = ManufacturerProductType(
    value="Pharmaceutical Stoppering Station")
nameplate.country_of_origin = CountryOfOrigin(value="DE")
# arbitrary_property is a multi-cardinality map
nameplate.asset_specific_properties = AssetSpecificProperties(
    arbitrary_property={
        "process_cell": ArbitraryProperty(value="ProcessCell: InnoLab Line 1")
    }
)

# ── Capability Description ──
capability_desc = CapabilityDescription(
    id_short="CapabilityDescription",
    id=sm_id("CapabilityDescription"),
)
# capability_set / capability_container are multi-cardinality maps → build the
# nested structure explicitly.
cc = CapabilityContainer(
    capability=Capability(semantic_id=f"{BASE_URL}/capabilities/Stoppering")
)
cc.capability_comment = CapabilityComment(
    value={"en": "Places rubber stoppers into vials at up to 120 ppm"}
)
cc.capability_relations = CapabilityRelations(
    capability_realized_by={
        "capability_realized_by": CapabilityRealizedBy(
            first=ModelReference(
                key=(Key(type_="Submodel", value=sm_id("CapabilityDescription")),)
            ),
            second=ExternalReference(
                key=(Key(type_="GlobalReference", value=sm_id("ControlComponentInstance")),)
            ),
        )
    }
)
capability_desc.capability_set = {
    "capability_set": CapabilitySet(
        capability_container={"capability_container": cc}
    )
}

def _make_skill() -> ExtendedSkill:
    """Skill with template-default metadata; only the runtime value is set."""
    skill = ExtendedSkill()
    skill.disabled.value = "false"
    return skill

# ── Control Component Instance (Pattern 2: explicit model instances) ──
cci = ControlComponentInstance(
    id_short="ControlComponentInstance",
    id=sm_id("ControlComponentInstance"),
    type=Type_instance(
        value=ModelReference(
            key=(Key(
                type_="Submodel",
                value=f"{BASE_URL}/submodels/instances/{ASSET_ID}/ControlComponentType",
            ),)
        )
    ),
    endpoints=Endpoints(
        endpoint={
            "endpoint": Endpoint(
                interface_reference=InterfaceReference(
                    value=ExternalReference(
                        key=(Key(
                            type_="GlobalReference",
                            value="https://admin-shell.io/idta/ControlComponent/Interface/MQTT/1/0",
                        ),)
                    )
                ),
                endpoint_reference=EndpointReference(
                    value=ExternalReference(
                        key=(Key(
                            type_="GlobalReference",
                            value="mqtt://192.168.0.104:1883/InnoLab/Stoppering",
                        ),)
                    )
                ),
            )
        }
    ),
    skills=Skills(skill={"skill": _make_skill()}),
)

# ═══════════════════════════════════════════════════════════════════════
# Convert → basyx
# ═══════════════════════════════════════════════════════════════════════
print("=" * 62)
print("  IDTA-Compliant AAS — built from generated templates")
print("=" * 62)

models = {
    "Digital Nameplate (IDTA 02006-3-0)": nameplate,
    "Capability Description (IDTA 02020-1-0)": capability_desc,
    "Control Component Instance (IDTA 02016-2-0)": cci,
}

for label, pydantic_sm in models.items():
    basyx_sm = convert_model_to_submodel(pydantic_sm)
    elements = basyx_sm.submodel_element
    sid = basyx_sm.semantic_id
    sid_val = sid.key[0].value if sid and sid.key else "(none)"
    print(f"\n{label}")
    print(f"  id_short : {basyx_sm.id_short}")
    print(f"  semantic : {sid_val}")
    print(f"  children : {[el.id_short for el in elements]}")
