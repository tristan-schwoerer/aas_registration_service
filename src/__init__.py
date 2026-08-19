"""
Registration Service Package

Registration service for BaSyx.

Responsibilities (the AAS is THE ONLY TRUTH):
- Convert IDTA templates into Pydantic classes (see third_party/aas_pydantic)
- Modify/extend/add Pydantic classes to define submodel/asset templates
- Generate a JSON template for asset templates
- Deep-merge the filled-out asset template with the JSON config received via MQTT
- Post the AAS to BaSyx
"""

from .config import BaSyxConfig
from .utils import save_json_file, load_json_file, ensure_directory

# Core utilities
from .core import (
    HTTPClient,
    HTTPError,
    DEFAULT_MQTT_BROKER,
    DEFAULT_MQTT_PORT,
    DEFAULT_BASYX_URL,
    ModelType,
    HTTPStatus,
    BaSyxEndpoints,
)

# Utility functions
from .utils import (
    encode_aas_id,
    sanitize_id,
    topic_to_id,
)

# Config parsing (deep merge + validation only)
from .config_parser import (
    parse_config_file, parse_config_data,
)

# Registration service
from .registration_service import RegistrationService
from .mqtt_config_registration import MQTTConfigRegistrationService

# AAS Generation — IDTA-compliant via aas_pydantic
from .aas_idta import (
    build_from_dict, build_from_json, build_resource_type_aas,
    generate_station_template, inject_ids,
    ResourceTypeAAS, templates as idta_templates,
)

__all__ = [
    # Core
    'BaSyxConfig',
    'save_json_file', 'load_json_file', 'ensure_directory',
    # Core utilities
    'HTTPClient', 'HTTPError',
    'DEFAULT_MQTT_BROKER', 'DEFAULT_MQTT_PORT', 'DEFAULT_BASYX_URL',
    'ModelType', 'HTTPStatus', 'BaSyxEndpoints',
    # Utility functions
    'encode_aas_id', 'sanitize_id', 'topic_to_id',
    # Config parsing
    'parse_config_file', 'parse_config_data',
    # Registration service
    'RegistrationService',
    'MQTTConfigRegistrationService',
    # AAS Generation
    'build_from_dict', 'build_from_json',
    'build_resource_type_aas', 'generate_station_template', 'inject_ids',
    'ResourceTypeAAS', 'idta_templates',
]
