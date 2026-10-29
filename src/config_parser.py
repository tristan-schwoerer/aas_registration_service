"""Load and directly validate exported Resource model JSON.

The JSON is an interchange representation of a Python-authored Resource, not
a partial configuration to merge with defaults. Build-time ID resolution is
owned by ``aas_model.build_from_model``.

Usage::

    from src.config_parser import parse_config_file, parse_config_data

    asset = parse_config_file("my_asset.json")
"""

from __future__ import annotations

import copy
from typing import Any, Dict

from aas_model import Resource


def parse_config_file(path: str) -> Resource:
    """Load an exported Resource JSON file and validate it without mutation."""
    with open(path, encoding="utf-8") as file:
        return Resource.model_validate_json(file.read())


def parse_config_data(data: Dict[str, Any]) -> Resource:
    """Validate an exported Resource model without merging or enriching it."""
    return Resource.model_validate(copy.deepcopy(data))
