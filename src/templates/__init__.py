"""
templates — IDTA-compliant AAS construction using aas_pydantic Pydantic models.

Users define AAS instances as JSON dicts matching the Pydantic model schema.
Pydantic validates + coerces values; builder converts to BaSyx.

Quick start::

    from src.templates import build_from_dict, ResourceTypeAAS
    obj_store = build_from_dict(json.load(open("my_asset.json")))
"""

from .builder import (
    build_from_dict,
    build_from_json,
    build_resource_type_aas,
    generate_station_template,
)
from .id_injector import inject_ids
from .json_schema_aid import datapoint_from_schema, load_schema, populate_datapoint
from .resource_template import ResourceTypeAAS
from . import submodel_templates as templates

__all__ = [
    "build_from_dict",
    "build_from_json",
    "build_resource_type_aas",
    "generate_station_template",
    "inject_ids",
    "datapoint_from_schema",
    "load_schema",
    "populate_datapoint",
    "ResourceTypeAAS",
    "templates",
]
