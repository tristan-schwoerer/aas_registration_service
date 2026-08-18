"""
Constants and configuration values for the Registration Service.

Centralizes magic strings, default values, and configuration constants.
"""

from enum import Enum
from typing import Final
import os

# SemanticIdCatalog removed — semantic IDs are inline on Pydantic models.
# See src/aas_idta/ for the IDTA-compliant replacements.


# Default network configuration
# These defaults are for running outside Docker (e.g., register_all_assets.py)
# Docker containers have MQTT_BROKER hardcoded to hivemq-broker in docker-compose.yml
DEFAULT_MQTT_BROKER: Final[str] = os.environ.get(
    "MQTT_BROKER", "localhost")
DEFAULT_MQTT_PORT: Final[int] = int(os.environ.get("MQTT_PORT", "1883"))
DEFAULT_BASYX_URL: Final[str] = os.environ.get(
    "BASYX_URL", "http://aas-env:8081")
DEFAULT_BASYX_INTERNAL_URL: Final[str] = os.environ.get(
    "BASYX_INTERNAL_URL", "http://aas-env:8081")
DEFAULT_GITHUB_PAGES_URL: Final[str] = "https://aausmartproductionlab.github.io/AP2030-UNS"

# External URL for registry descriptors (used for URLs that need to be accessed from outside Docker)
EXTERNAL_BASYX_HOST: Final[str] = os.environ.get("EXTERNAL_HOST", "localhost")


class ModelType(str, Enum):
    """AAS model types."""
    AAS = "AssetAdministrationShell"
    SUBMODEL = "Submodel"
    CONCEPT_DESCRIPTION = "ConceptDescription"
    PROPERTY = "Property"
    FILE = "File"
    OPERATION = "Operation"
    SUBMODEL_COLLECTION = "SubmodelElementCollection"
    SUBMODEL_LIST = "SubmodelElementList"


class HTTPStatus(int, Enum):
    """Common HTTP status codes."""
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    NOT_FOUND = 404
    CONFLICT = 409


class BaSyxEndpoints:
    """BaSyx endpoint paths."""
    SHELLS: Final[str] = "/shells"
    SUBMODELS: Final[str] = "/submodels"
    CONCEPT_DESCRIPTIONS: Final[str] = "/concept-descriptions"
    SHELL_DESCRIPTORS: Final[str] = "/shell-descriptors"
    SUBMODEL_DESCRIPTORS: Final[str] = "/submodel-descriptors"


class BaSyxPorts:
    """BaSyx service ports."""
    AAS_ENV: Final[int] = 8081
    AAS_REGISTRY: Final[int] = 8082
    SUBMODEL_REGISTRY: Final[int] = 8083


class PathDefaults:
    """Default paths for configuration files."""
    CONFIG_DIR: Final[str] = "AASDescriptions/Resource/configs"


class MQTTTopics:
    """Default MQTT topics."""
    # Single registration topic - asset identity is determined from YAML payload
    REGISTRATION_CONFIG: Final[str] = "NN/Nybrovej/InnoLab/Registration/Config"
    REGISTRATION_RESPONSE: Final[str] = "NN/Nybrovej/InnoLab/Registration/Response"


class TimeoutDefaults:
    """Default timeout values in seconds."""
    HTTP_REQUEST: Final[int] = 10
    MQTT_CONNECT: Final[int] = 60
