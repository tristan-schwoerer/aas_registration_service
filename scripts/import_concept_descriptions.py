#!/usr/bin/env python3
"""
Import Concept Descriptions from the IDTA submodel templates into BaSyx.

The generated AAS models carry semanticIds (e.g. ``https://www.w3.org/2011/
http#headers``) but no Concept Descriptions themselves — the fork's
serialization emits ``conceptDescriptions: []``.  The AAS GUI therefore
404s when it looks up a concept description for every element it renders.

This script registers the ``conceptDescriptions`` bundled in the vendored
IDTA templates (the same 7 the generator builds from) into the BaSyx
concept-description repository, so those lookups resolve.

Usage::

    cd Registration_Service
    python scripts/import_concept_descriptions.py
    python scripts/import_concept_descriptions.py --basyx-url http://localhost:8081
"""

import argparse
import base64
import json
import os
import sys

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "third_party", "aas_pydantic"))

# The IDTA templates the generator builds from — their conceptDescriptions
# cover the semanticIds the generated AASs reference.
TEMPLATES = [
    "submodel-templates/published/Capability Description/1/0/IDTA 02020_Template_Capability_Description.json",
    "submodel-templates/published/Control Component Instance/2/0/1/IDTA 02016-2-0-1 _Template_ControlComponentInstance_forAASMetamodelV3.1.json",
    "submodel-templates/published/Control Component Type/2/0/1/IDTA 02015-2-0-1 _Template_ControlComponentType_forAASMetamodelV3.1.json",
    "submodel-templates/published/Hierarchical Structures enabling Bills of Material/1/1/1/IDTA 02011-1-1-1_Template_HSEBoM_forAASMetamodelV3.1.json",
    "submodel-templates/published/Digital nameplate/3/0/1/IDTA 02006-3-0-1_Template_Digital Nameplate.json",
    "submodel-templates/published/Asset Interfaces Mapping Configuration/2/0/IDTA 02027_Template_AIMC.json",
    "submodel-templates/published/Asset Interfaces Description/1/1/IDTA 02017-1-1_Template_Asset Interfaces Description.json",
]

_TEMPLATES_ROOT = os.path.join(
    _HERE, "..", "third_party", "aas_pydantic", "submodel-templates", "published"
)


def collect_concept_descriptions() -> dict:
    """All template conceptDescriptions, deduplicated by id."""
    cds = {}
    for rel in TEMPLATES:
        path = os.path.join(_TEMPLATES_ROOT, rel.replace("submodel-templates/published/", ""))
        if not os.path.exists(path):
            print(f"⚠️  missing template: {rel}")
            continue
        with open(path) as f:
            data = json.load(f)
        for cd in data.get("conceptDescriptions", []):
            cds.setdefault(cd["id"], cd)
    return cds


def referenced_semantic_ids(aas_json_path: str) -> set:
    """Every semanticId / data-specification reference in a serialized AAS."""
    with open(aas_json_path) as f:
        data = json.load(f)
    sids = set()

    def walk(el):
        if isinstance(el, dict):
            s = el.get("semanticId")
            if isinstance(s, dict):
                for k in s.get("keys", []):
                    if k.get("value"):
                        sids.add(k["value"])
            for ds in (el.get("embeddedDataSpecifications") or []):
                for k in (ds.get("dataSpecification", {}).get("keys") or []):
                    if k.get("value"):
                        sids.add(k["value"])
            for v in el.values():
                walk(v)
        elif isinstance(el, list):
            for x in el:
                walk(x)

    walk(data)
    return sids


def minimal_concept_description(sid: str) -> dict:
    """A minimal IEC61360 ConceptDescription for a semanticId (used for the
    project's own extension concepts — ``smartproductionlab.aau.dk/*`` — and
    for any referenced concept the IDTA templates don't ship).  The preferred
    name is derived from the last meaningful URI segment."""
    frag = sid.split("#")[-1] if "#" in sid else ""
    parts = [p for p in sid.split("#")[0].split("/") if p and not p.isdigit()]
    name = frag if frag else (parts[-1] if parts else sid)
    return {
        "idShort": name[:128],
        "id": sid,
        "modelType": "ConceptDescription",
        "embeddedDataSpecifications": [
            {
                "dataSpecification": {
                    "type": "ExternalReference",
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3/0",
                        }
                    ],
                },
                "dataSpecificationContent": {
                    "preferredName": [{"language": "en", "text": name}],
                    "modelType": "DataSpecificationIec61360",
                },
            }
        ],
    }


def import_concept_descriptions(base_url: str, cds: dict) -> dict:
    url = f"{base_url.rstrip('/')}/concept-descriptions"
    ok = conflict = failed = 0

    for cd_id, cd in cds.items():
        enc = base64.b64encode(cd_id.encode()).decode()
        cd.setdefault("modelType", "ConceptDescription")
        try:
            response = requests.post(url, json=cd, timeout=10)
            if response.status_code in (200, 201):
                ok += 1
                continue
            if response.status_code == 409:
                # exists → replace with the (possibly updated) copy
                requests.delete(f"{url}/{enc}", timeout=10)
                response = requests.post(url, json=cd, timeout=10)
                if response.status_code in (200, 201):
                    conflict += 1
                else:
                    failed += 1
                    print(f"  ✗ re-post failed {cd_id}: {response.status_code}")
            else:
                failed += 1
                print(f"  ✗ {cd_id}: {response.status_code} {response.text[:120]}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ✗ {cd_id}: {e}")

    return {"total": len(cds), "ok": ok, "updated": conflict, "failed": failed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basyx-url", default=os.environ.get("BASYX_URL", "http://localhost:8081"))
    parser.add_argument(
        "--aas",
        help="A serialized AAS JSON (e.g. from ``json_serialization.object_store_to_json``); "
        "also registers minimal ConceptDescriptions for every referenced semanticId "
        "the IDTA templates don't ship (project-specific extensions).",
    )
    args = parser.parse_args()

    cds = collect_concept_descriptions()
    print(f"collected {len(cds)} concept descriptions from IDTA templates")

    if args.aas:
        refs = referenced_semantic_ids(args.aas)
        generated = {sid for sid in refs if sid not in cds}
        for sid in sorted(generated):
            cds[sid] = minimal_concept_description(sid)
        print(f"AAS references {len(refs)} semanticIds; auto-generated {len(generated)} minimal CDs")

    result = import_concept_descriptions(args.basyx_url, cds)
    print(
        f"✓ registered {result['ok']} (new), {result['updated']} (updated), "
        f"{result['failed']} failed of {result['total']}"
    )
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
