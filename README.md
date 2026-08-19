# Registration Service

Registers Asset Administration Shells (AAS) from JSON configuration files.

The registration service has exactly **five responsibilities** — the published
AAS is the single source of truth for all downstream services:

1. Convert IDTA templates into Pydantic classes (`third_party/aas_pydantic/scripts/idta_generate.py`)
2. Modify / extend / add Pydantic classes to define submodel and asset templates (`src/templates/`)
3. Generate a JSON template for asset templates (`generate_station_template`)
4. Deep-merge the filled-out asset template with the JSON config received via MQTT (`config_parser.parse_config_data`)
5. Post the AAS to BaSyx

All former "processing" (topics.json for Operation Delegation, DataBridge
config generation, schema/endpoint extraction) has been **removed** — operation
delegation, controller, planner and DataBridge are reworked as standalone
services that read the AAS directly and subscribe to registration events.

## Repository layout

This is a standalone repository. It is consumed as a git submodule by
`AP2030-UNS` (at `Registration_Service/`) — the AAS configs stay asset-side in
`AP2030-UNS/AASDescriptions/Resource/configs` and are mounted into the
container at runtime.

Submodules:

- `third_party/aas_pydantic` — the (forked) pydantic↔BaSyx conversion layer +
  the IDTA template generator (`scripts/idta_generate.py`)
- `MQTTSchemas` — the `mqtt_message_schemas` repo (JSON schemas for MQTT
  messages; mapped from the `.../github.io/.../MQTTSchemas/` URL namespace by
  `src/schema_parser.py`, overridable via the `MQTT_SCHEMAS_DIR` env var)

## Setup

```bash
git clone git@github.com:tristan-schwoerer/aas_registration_service.git
cd aas_registration_service
git submodule update --init --recursive
pip install -r requirements.txt
```

## Features

- **Config-based Registration**: Register assets from JSON configuration files matching the `ResourceTypeAAS` schema
- **Deep-Merge + Strict Validation**: The config is deep-merged with the asset template and validated against the Pydantic model — unknown/clashing keys fail loudly
- **AAS Generation**: Generates full AAS descriptions via the Pydantic → aas_pydantic → BaSyx pipeline
- **BaSyx Registration**: Registers Shells, Submodels, and Concept Descriptions with BaSyx (repositories + registries)
- **MQTT Listener**: Listens for registration requests via MQTT for dynamic asset onboarding

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Register from a JSON config

```bash
# In Docker (aas-env / aas-registry / sm-registry resolve on the network)
python registration-service.py register-config AASDescriptions/Resource/configs/syntegonStoppering.json

# From the host (pass the registry URLs explicitly — global options come
# before the subcommand)
python registration-service.py \
  --basyx-url http://localhost:8081 \
  --aas-registry-url http://localhost:8082 \
  --sm-registry-url http://localhost:8083 \
  register-config \
  ../AASDescriptions/Resource/configs/syntegonStoppering.json

# Register all configs from a directory
python registration-service.py register-dir AASDescriptions/Resource/configs/
```

### MQTT Listener

Start the service in listening mode to accept dynamic registration requests:

```bash
python registration-service.py listen \
  --mqtt-broker 192.168.0.104 \
  --mqtt-port 1883 \
  --basyx-url http://localhost:8081
```

Each received config message is deep-merged with the asset template, built into
an AAS and posted to BaSyx.

#### MQTT Message Formats

**Config-based registration** (preferred, on topic `NN/Nybrovej/InnoLab/Registration/Config`):
```json
{
  "requestId": "unique-id",
  "assetId": "syntegonStopperingSystemAAS",
  "config": {
    "idShort": "syntegonStopperingSystemAAS",
    "id": "https://smartproductionlab.aau.dk/aas/syntegonStopperingSystemAAS",
    ...
  }
}
```

**Legacy AAS JSON** (on topic `NN/Nybrovej/InnoLab/Registration/Request`):
```json
{
  "requestId": "unique-id",
  "assetId": "syntegonStopperingSystemAAS",
  "aasData": {
    "assetAdministrationShells": [...],
    "submodels": [...]
  }
}
```

### List registered AAS

```bash
python registration-service.py list
```

## Architecture

The registration service consists of:

1. **config_parser**: Deep-merges the JSON config with the asset template, validates against `ResourceTypeAAS`, injects IDs and enriches config-declared AID datapoints with their JSON Schema structures
2. **RegistrationService**: Orchestrates the registration workflow (parse → build AAS → post to BaSyx)
3. **MQTTConfigRegistrationService**: MQTT listener for dynamic registration

### Workflow

```
JSON Config → Deep-merge with asset template → Pydantic validation → AAS (aas_pydantic → BaSyx JSON) → Post to BaSyx
```

## Configuration

The service interacts with the following components (defaults):
- **BaSyx Environment**: `http://localhost:8081`
- **MQTT Broker**: `192.168.0.104:1883`

### Environment Variables

- `BASYX_URL`: BaSyx server URL
- `MQTT_BROKER`: MQTT broker hostname
- `MQTT_PORT`: MQTT broker port

## Skills YAML Simplification

The Skills parser supports simplified action semantics in `pddl`.

### Recommended simplified syntax

```yaml
Skills:
  - key: Loading
    InterfaceReference: Loading
    pddl:
      parameters:
        - name: LoadingSystem
          modelRef:
            - AAS: self
        - name: Product
          externalRef: https://smartproductionlab.aau.dk/Product
        - name: TransportSystem
          externalRef: https://smartproductionlab.aau.dk/CPS/Transport

      duration:
        =:
          left:
            func:
              external: https://smartproductionlab.aau.dk/PDDL/Functions/Duration
              args: [0]
          right:
            const: 5.0

      conditions:
        at_start:
          and:
            - pred:
                ref: Operational
                args: [0]
            - pred:
                ref: Occupied
                args: [0, 1]

      effects:
        at_end:
          and:
            - set:
                pred:
                  external: https://smartproductionlab.aau.dk/PDDL/Term/Predicates/On
                  args: [1, 2]
                value: true
            - set:
                pred:
                  external: https://smartproductionlab.aau.dk/PDDL/Term/Predicates/At
                  args: [1, 0]
                value: true

```

Use this structure for new and existing Skills configs. Legacy `skill_description`
syntax is no longer supported.

Only action semantics are emitted in Skills:
- `parameters`
- `duration`
- `conditions`
- `effects`

For compatibility, unsupported extended fields such as `processes`, `events`,
`constraints`, and `preferences` are ignored when present in Skills config.

