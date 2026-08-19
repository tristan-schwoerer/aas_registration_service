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

logger = logging.getLogger(__name__)


def parse_config_file(path: str) -> ResourceTypeAAS:
    """Load JSON config file, validate, inject IDs, return ResourceTypeAAS."""
    with open(path) as f:
        return parse_config_data(json.load(f))


def parse_config_data(data: Dict[str, Any]) -> ResourceTypeAAS:
    """Validate against ResourceTypeAAS (base defaults merged under the
    instance config — so specialized types survive and omitted fields fall
    back to defaults), inject IDs, return model instance.

    Config-declared AID datapoints (action ``input``/``output`` DataSchemas,
    property payload schemas) that carry a JSON Schema URL as their
    supplemental semantic id are populated from that schema."""
    asset = ResourceTypeAAS.model_validate(merge_instance_config(data))
    inject_ids(asset)
    if asset.asset_interfaces_description is not None:
        ensure_aid_datapoint_schemas(asset.asset_interfaces_description)
    return asset

