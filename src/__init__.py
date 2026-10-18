"""
Registration Service Package

Registration service for BaSyx.

Responsibilities (the AAS is THE ONLY TRUTH):
- Validate exported Python-authored Resource models
- Build and post the AAS to BaSyx
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

# Config parsing (validation only)
from .config_parser import (
    parse_config_file, parse_config_data,
)

# Registration service
from .registration_service import RegistrationService
from .mqtt_config_registration import MQTTConfigRegistrationService

# AAS Generation — the shared data-model package (ADR-016)
from aas_model import Resource, build_from_model
from aas_model import submodel_templates as idta_templates

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
    'Resource', 'build_from_model', 'idta_templates',
]
