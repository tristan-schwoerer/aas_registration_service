"""
Asset Config — load JSON, validate against ResourceTypeAAS.

The Pydantic model IS the config.  JSON must match the ResourceTypeAAS schema.
id_short and id are auto-injected post-validation via the id_injector module.

This module is deliberately minimal: its only job is to turn the received JSON
config into a validated, fully-populated ``ResourceTypeAAS`` instance — deep
merging the filled-out asset template under the instance config, injecting
IDs, and enriching config-declared AID datapoints with their JSON Schema
structures.  All further parsing/processing (topics.json, operation-delegation
entries, DataBridge mappings, …) has been REMOVED from the registration
service: downstream services read the published AAS as the single source of
truth.

Usage::

    from src.config_parser import parse_config_file, parse_config_data

    asset = parse_config_file("my_asset.json")
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from .templates.resource_template.asset import ResourceTypeAAS
from .templates.resource_template.asset_interfaces_description import (
    ensure_aid_datapoint_schemas,
)
from .templates.builder import merge_instance_config
from .templates.id_injector import inject_ids
from .templates.constants import DELEGATION_BASE
from .templates.resource_template.property_delegation import (
    ensure_property_write_delegation,
)

logger = logging.getLogger(__name__)


def parse_config_file(path: str) -> ResourceTypeAAS:
    """Load JSON config file, validate, inject IDs, return ResourceTypeAAS."""
    with open(path) as f:
        return parse_config_data(json.load(f))


def parse_config_data(data: Dict[str, Any]) -> ResourceTypeAAS:
    """Validate against ResourceTypeAAS (base defaults merged under the
    instance config — so specialized types survive and omitted fields fall
    back to defaults), inject IDs, return model instance.

    The optional top-level ``delegation_base`` config key overrides the
    resource's DMP / operation-delegation base URL (defaults to
    ``constants.DELEGATION_BASE``); it is resolved into the skill Operation
    ``invocationDelegation`` qualifiers and the AID REST interface base.

    Config-declared AID datapoints (action ``input``/``output`` DataSchemas,
    property payload schemas) that carry a JSON Schema URL as their
    supplemental semantic id are populated from that schema."""
    delegation_base = data.get("delegation_base") or DELEGATION_BASE
    asset = ResourceTypeAAS.model_validate(merge_instance_config(data))
    # Property write-delegation: any property carrying a ``writeDelegation``
    # qualifier gets its REST write interface + AIMC mapping auto-wired
    # (before id injection so the ``{delegation_base}``/``{aas_id_short}``
    # macros resolve).
    ensure_property_write_delegation(asset)
    inject_ids(asset, delegation_base=delegation_base)
    if asset.asset_interfaces_description is not None:
        ensure_aid_datapoint_schemas(asset.asset_interfaces_description)
    return asset

