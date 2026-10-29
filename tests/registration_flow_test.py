#!/usr/bin/env python3
"""
Registration Service Integration Test

Tests the registration flow against the current Python-authored Resource model:

1. Config parsing (direct Resource validation)
2. AAS generation (build_from_model → BaSyx store)
3. Full registration (optional - requires BaSyx)

Runs under pytest (``python -m pytest tests/registration_flow_test.py``) or
standalone (``python tests/registration_flow_test.py``).
"""

from __future__ import annotations

import os
import json
import sys
from pathlib import Path

import pytest

# Add repo + src to path (so the script works standalone too)
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from src import (  # noqa: E402
    BaSyxConfig,
    RegistrationService,
)
from src.config_parser import parse_config_data  # noqa: E402
from aas_model import build_from_model  # noqa: E402
from aas_model.resource_instances.stopperingModule import syntegon_stoppering  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def resource_data():
    return json.loads(syntegon_stoppering().model_dump_json())


@pytest.fixture(scope="module")
def asset(resource_data):
    return parse_config_data(resource_data)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Config parsing
# ═══════════════════════════════════════════════════════════════════════════════

def test_config_parsing(asset):
    assert asset.id_short == "syntegonStopperingSystemAAS"
    assert asset.id.startswith("https://")

    # The AAS carries the runtime semantics itself — the AID submodel embeds
    # the MQTT base URI, action/property affordances and schema URLs.
    assert asset.asset_interfaces_description is not None


def test_config_parsing_preserves_the_complete_export(resource_data):
    asset = parse_config_data(resource_data)

    assert json.loads(asset.model_dump_json()) == resource_data


def test_config_parsing_does_not_restore_removed_resource_elements():
    resource = syntegon_stoppering()
    resource.variables.State.value.clear()
    resource.parameters.parameter.clear()
    resource.control_component_instance.Skills.Skill.pop("Halt")
    data = json.loads(resource.model_dump_json())
    asset = parse_config_data(data)

    assert asset.variables.State.value == {}
    assert asset.parameters.parameter == {}
    assert "Halt" not in asset.control_component_instance.Skills.Skill
    assert json.loads(asset.model_dump_json()) == data


def test_config_parsing_does_not_enrich_schema_or_mqtt_terms(monkeypatch):
    from aas_model.submodel_templates.aid import DmpActionInput

    resource = syntegon_stoppering()
    action = resource.asset_interfaces_description.InterfaceTemplateForMQTT[
        "interface_mqtt"
    ].InteractionMetadata.actions.property_name["Stoppering"]
    action.input = DmpActionInput(
        id_short="input", supplemental_semantic_ids=["https://example.invalid/schema.json"],
    )
    action.forms.mqv_responseTopic = None
    data = json.loads(resource.model_dump_json())

    def unexpected_schema_load(*args, **kwargs):
        raise AssertionError("Registration must not fetch authoring schemas")

    monkeypatch.setattr("aas_model.json_schema_aid.load_schema", unexpected_schema_load)
    asset = parse_config_data(data)

    assert json.loads(asset.model_dump_json()) == data


def test_aas_generation_receives_the_validated_model(monkeypatch):
    import src.registration_service as registration_service

    asset = syntegon_stoppering()
    store = object()
    seen = []
    monkeypatch.setattr(registration_service, "build_from_model", lambda value: seen.append(value) or store)
    monkeypatch.setattr(
        "aas_pydantic.convert_util.strip_temp_id_short_attributes", lambda value: None,
    )
    monkeypatch.setattr(
        "basyx.aas.adapter.json.json_serialization.object_store_to_json",
        lambda value: "{}",
    )

    result = RegistrationService()._generate_aas(asset)

    assert result == {}
    assert seen == [asset]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. AAS generation
# ═══════════════════════════════════════════════════════════════════════════════

def test_aas_generation(asset):
    store = build_from_model(asset)

    shells = [o for o in store if o.__class__.__name__ == "AssetAdministrationShell"]
    submodels = [o for o in store if o.__class__.__name__ == "Submodel"]

    assert len(shells) == 1
    shell = shells[0]
    assert shell.id_short == "syntegonStopperingSystemAAS"
    assert shell.id

    sm_ids = {sm.id_short for sm in submodels}
    assert sm_ids >= {
        "Nameplate",
        "AssetInterfacesDescription",
        "ControlComponentInstance",
        "CapabilityDescription",
        "Variables",
        "Parameters",
    }

    # AID must carry the MQTT actions, each with a form (WoT: an action's op
    # defaults to invokeaction, so the form need not state it)
    aid = next(sm for sm in submodels if sm.id_short == "AssetInterfacesDescription")
    mqtt = next(el for el in aid.submodel_element if el.id_short == "interface_mqtt")
    metadata = next(el for el in mqtt.value if el.id_short == "InteractionMetadata")
    actions = next(el for el in metadata.value if el.id_short == "actions")
    assert {a.id_short for a in actions.value} >= {"Halt", "Occupy", "Release", "Stoppering"}
    for action in actions.value:
        forms = next(el for el in action.value if el.id_short == "forms")
        href = next(el for el in forms.value if el.id_short == "href")
        assert href.value == f"CMD/{action.id_short}"

    # Parameters.Location must carry its children (x/y/yaw)
    parameters = next(sm for sm in submodels if sm.id_short == "Parameters")
    location = next(
        (el for el in parameters.submodel_element if el.id_short == "Location"),
        None,
    )
    assert location is not None
    child_ids = {c.id_short for c in location.value}
    assert {"x", "y", "yaw"} <= child_ids


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Full registration (optional - requires BaSyx)
# ═══════════════════════════════════════════════════════════════════════════════

def _default_basyx_url() -> str:
    """BaSyx AAS server URL for the full-registration test.

    The compose stack publishes the AAS environment on the host's 8081, so
    ``http://localhost:8081`` is the default.  Set ``BASYX_URL`` (e.g.
    ``http://aas-env:8081``) when running the tests inside the Docker network.
    """
    return os.environ.get("BASYX_URL", "http://localhost:8081")


@pytest.mark.skipif(
    os.environ.get("RUN_BASYX_INTEGRATION") != "1",
    reason="Set RUN_BASYX_INTEGRATION=1 to publish to a live BaSyx server",
)
def test_full_registration(resource_data, basyx_url: str = ""):
    """Register against a live BaSyx server only when explicitly enabled."""
    basyx_url = basyx_url or _default_basyx_url()
    try:
        import requests
        try:
            response = requests.get(f"{basyx_url}/shells", timeout=5)
            if response.status_code not in [200, 401]:
                pytest.skip(f"BaSyx returned status {response.status_code}")
        except requests.exceptions.ConnectionError:
            pytest.skip(f"Cannot connect to BaSyx at {basyx_url}")
    except ImportError:
        pytest.skip("requests not installed")

    service = RegistrationService(
        config=BaSyxConfig(base_url=basyx_url),
    )
    assert service.register_from_data(resource_data)


# ═══════════════════════════════════════════════════════════════════════════════
# Standalone CLI (pytest-compatible — pytest skips non-test helpers)
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test Registration Service Flow")
    parser.add_argument("--config", help="Optional exported Resource JSON file")
    parser.add_argument("--with-basyx", action="store_true")
    parser.add_argument("--basyx-url", default=_default_basyx_url())
    args = parser.parse_args()

    results = {}
    try:
        if args.config:
            from src.config_parser import parse_config_file
            asset = parse_config_file(args.config)
            resource_data = asset.model_dump(mode="json")
        else:
            resource_data = json.loads(syntegon_stoppering().model_dump_json())
            asset = parse_config_data(resource_data)
        results["config_parsing"] = "PASSED"
        print("config parsing: PASSED")

        store = build_from_model(asset)
        shells = [o for o in store if o.__class__.__name__ == "AssetAdministrationShell"]
        submodels = [o for o in store if o.__class__.__name__ == "Submodel"]
        results["aas_generation"] = "PASSED" if shells and len(submodels) >= 5 else "FAILED"
        print(f"aas generation: {results['aas_generation']} ({len(shells)} shells, {len(submodels)} submodels)")

        if args.with_basyx:
            service = RegistrationService(
                config=BaSyxConfig(base_url=args.basyx_url),
            )
            results["full_registration"] = "PASSED" if service.register_from_data(resource_data) else "FAILED"
            print(f"full registration: {results['full_registration']}")
    finally:
        pass

    failed = [k for k, v in results.items() if v != "PASSED"]
    print(f"\nResults: {len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
