#!/usr/bin/env python3
"""
Registration Service Integration Test

Tests the registration flow against the current ResourceTypeAAS (JSON)
pipeline:

1. Config parsing (parse_config_file — deep merge + validation)
2. AAS generation (build_from_json → BaSyx store)
3. Full registration (optional - requires BaSyx)

Runs under pytest (``python -m pytest tests/registration_flow_test.py``) or
standalone (``python tests/registration_flow_test.py``).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Add repo + src to path (so the script works standalone too)
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parent / "third_party" / "aas_pydantic"))

from src import (  # noqa: E402
    BaSyxConfig,
    RegistrationService,
)
from src.config_parser import parse_config_file  # noqa: E402
from src.templates.builder import build_from_json  # noqa: E402

# The current Resource config (JSON, ResourceTypeAAS schema).  Defaults to the
# AP2030-UNS asset config (this repo is consumed as a submodule at
# Registration_Service/ in AP2030-UNS); override with AAS_TEST_CONFIG.
CONFIG_PATH = os.environ.get(
    "AAS_TEST_CONFIG",
    str(
        _HERE.parent.parent
        / "AASDescriptions"
        / "Resource"
        / "configs"
        / "syntegonStoppering.json"
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def config_path() -> Path:
    path = Path(CONFIG_PATH)
    if not path.exists():
        pytest.skip(f"config not found: {path}")
    return path


@pytest.fixture(scope="module")
def asset(config_path: Path):
    return parse_config_file(str(config_path))


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Config parsing
# ═══════════════════════════════════════════════════════════════════════════════

def test_config_parsing(asset):
    assert asset.id_short == "syntegonStopperingSystemAAS"
    assert asset.id.startswith("https://")

    # The AAS carries the runtime semantics itself — the AID submodel embeds
    # the MQTT base URI, action/property affordances and schema URLs.
    assert asset.asset_interfaces_description is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. AAS generation
# ═══════════════════════════════════════════════════════════════════════════════

def test_aas_generation(config_path: Path):
    store = build_from_json(str(config_path))

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
        "Variables",
        "Parameters",
    }

    # AID must carry the MQTT actions + the WoT op field on forms
    aid = next(sm for sm in submodels if sm.id_short == "AssetInterfacesDescription")
    op_count = 0

    def _walk(el):
        nonlocal op_count
        if getattr(el, "id_short", "") == "op":
            op_count += 1
        value = getattr(el, "value", None)
        items = list(value) if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)) else []
        for child in items:
            _walk(child)

    for el in aid.submodel_element:
        _walk(el)
    assert op_count >= 4, "each action form must carry an op Property"

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


def test_full_registration(config_path: Path, basyx_url: str = ""):
    """Register the config against a live BaSyx server (requires the stack)."""
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
    assert service.register_from_config(str(config_path))


# ═══════════════════════════════════════════════════════════════════════════════
# Standalone CLI (pytest-compatible — pytest skips non-test helpers)
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test Registration Service Flow")
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--with-basyx", action="store_true")
    parser.add_argument("--basyx-url", default=_default_basyx_url())
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    results = {}
    try:
        asset = parse_config_file(str(config_path))
        results["config_parsing"] = "PASSED"
        print("config parsing: PASSED")

        store = build_from_json(str(config_path))
        shells = [o for o in store if o.__class__.__name__ == "AssetAdministrationShell"]
        submodels = [o for o in store if o.__class__.__name__ == "Submodel"]
        results["aas_generation"] = "PASSED" if shells and len(submodels) >= 5 else "FAILED"
        print(f"aas generation: {results['aas_generation']} ({len(shells)} shells, {len(submodels)} submodels)")

        if args.with_basyx:
            service = RegistrationService(
                config=BaSyxConfig(base_url=args.basyx_url),
            )
            results["full_registration"] = "PASSED" if service.register_from_config(str(config_path)) else "FAILED"
            print(f"full registration: {results['full_registration']}")
    finally:
        pass

    failed = [k for k, v in results.items() if v != "PASSED"]
    print(f"\nResults: {len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
