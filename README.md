# Registration Service

Registers Asset Administration Shells (AAS) from exported Python Resource models.

The registration service has **three responsibilities** — the published
AAS is the single source of truth for all downstream services:

1. Validate exported `Resource` JSON received via MQTT or from a file.
2. Build the AAS directly from the validated model using `aas_model.build_from_model`.
3. Post the AAS to BaSyx.

Authoring and exporting a `Resource` is not this service's job: resources are
defined with the `aas-model` package (`resource_template/`,
`resource_instances/`) and exported with its `scripts/export_resource.py`.

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

- `aas-model` — the shared AAS data-model package (ADR-016): the `Resource`
  model the service validates exports against and `build_from_model`. Its own
  submodules bring the IDTA `submodel-templates` and `MQTTSchemas`. The pinned
  commit is the model version the service accepts; advance it together with the
  stations that publish exports.

## Setup

```bash
git clone git@github.com:tristan-schwoerer/aas_registration_service.git
cd aas_registration_service
git submodule update --init --recursive
pip install ./aas-model -r requirements.txt
```

## Features

- **Model-based Registration**: Register assets from complete JSON exports of Python-authored `Resource` instances
- **Direct Validation**: Validate the authored structure without merging another resource into it or enriching its AID at registration time
- **AAS Generation**: Generates full AAS descriptions via the Pydantic → aas_pydantic → BaSyx pipeline
- **BaSyx Registration**: Registers Shells, Submodels, and Concept Descriptions with BaSyx (repositories + registries)
- **MQTT Listener**: Listens for registration requests via MQTT for dynamic asset onboarding

## Installation

```bash
pip install ./aas-model -r requirements.txt
```

## Usage

### Exported Resource JSON

The service registers the JSON export of a Python-authored `Resource`
(`aas-model`'s `scripts/export_resource.py`). JSON is an interchange format, not
a partial override language: the service validates it as a `Resource` without
merging defaults or enriching the AID. IDs and self-references are resolved
during the AAS build without modifying the imported model.

### Register from a JSON config

```bash
# In Docker (aas-env / aas-registry / sm-registry resolve on the network)
python registration-service.py register-config stoppering.export.json

# From the host (pass the registry URLs explicitly — global options come
# before the subcommand)
python registration-service.py \
  --basyx-url http://localhost:8081 \
  --aas-registry-url http://localhost:8082 \
  --sm-registry-url http://localhost:8083 \
  register-config \
  stoppering.export.json

# Register all exported configs from a directory
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

Each received model export is validated directly, built into an AAS and posted
to BaSyx. Its explicitly authored containers are not repopulated from defaults.

#### MQTT Message Formats

**Config-based registration** (preferred, on topic `NN/Nybrovej/InnoLab/Registration/Config`):
```python
import json
from aas_model.resource_instances.stopperingModule import syntegon_stoppering

resource = syntegon_stoppering()
request = {
    "requestId": "unique-id",
    "assetId": resource.id_short,
    "config": json.loads(resource.model_dump_json()),
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

1. **config_parser**: Uses native Pydantic validation for exported `Resource` JSON without merging, ID injection, URL-specific checks, or AID enrichment
2. **RegistrationService**: Orchestrates the registration workflow (parse → build AAS → post to BaSyx)
3. **MQTTConfigRegistrationService**: MQTT listener for dynamic registration

### Workflow

```
Python Resource -> JSON export -> Pydantic validation -> build_from_model -> BaSyx JSON -> Post to BaSyx
```

### Tests

```bash
python -m pytest -q
```

The default suite does not publish to a running BaSyx server. Enable the live
registration test explicitly with `RUN_BASYX_INTEGRATION=1`; `BASYX_URL` selects
the target. The tests import `aas_model` from the `aas-model` submodule.

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
