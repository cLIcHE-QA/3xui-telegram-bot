from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-3xui-openapi-contract.py"
MANIFEST = ROOT / "contracts" / "3xui" / "contract.json"

spec = importlib.util.spec_from_file_location("v417_openapi_gate", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load OpenAPI contract checker")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class OpenAPIContractGateTests(unittest.TestCase):
    def load_fixture(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        schema_path = ROOT / manifest["vendored_schema"]
        raw = schema_path.read_bytes()
        api = json.loads(raw.decode("utf-8"))
        return manifest, api, raw

    def test_pinned_contract_matches_schema_and_client_sources(self):
        self.assertEqual(gate.validate_contract(ROOT), [])

    def test_pinned_git_blob_sha_detects_schema_tampering(self):
        manifest, _, raw = self.load_fixture()
        self.assertEqual(
            gate.git_blob_sha(raw),
            manifest["upstream"]["schema_blob_sha"],
        )
        self.assertNotEqual(
            gate.git_blob_sha(raw + b"\n"),
            manifest["upstream"]["schema_blob_sha"],
        )

    def test_removed_http_method_fails_closed(self):
        manifest, api, _ = self.load_fixture()
        changed = copy.deepcopy(api)
        del changed["paths"]["/panel/api/clients/add"]["post"]

        errors = gate.validate_openapi_contract(
            manifest,
            changed,
            schema_blob_sha=manifest["upstream"]["schema_blob_sha"],
        )

        self.assertTrue(
            any(
                "OpenAPI missing method: POST /panel/api/clients/add" in item
                for item in errors
            ),
            errors,
        )

    def test_new_mandatory_request_field_fails_closed(self):
        manifest, api, _ = self.load_fixture()
        changed = copy.deepcopy(api)
        schema = changed["paths"]["/panel/api/clients/add"]["post"][
            "requestBody"
        ]["content"]["application/json"]["schema"]
        schema["required"] = ["client", "inboundIds", "tenantId"]

        errors = gate.validate_openapi_contract(
            manifest,
            changed,
            schema_blob_sha=manifest["upstream"]["schema_blob_sha"],
        )

        self.assertTrue(
            any(
                "required request fields drift for POST /panel/api/clients/add" in item
                for item in errors
            ),
            errors,
        )

    def test_response_envelope_property_removal_fails_closed(self):
        manifest, api, _ = self.load_fixture()
        changed = copy.deepcopy(api)
        props = changed["paths"]["/panel/api/server/status"]["get"][
            "responses"
        ]["200"]["content"]["application/json"]["schema"]["properties"]
        props.pop("obj")

        errors = gate.validate_openapi_contract(
            manifest,
            changed,
            schema_blob_sha=manifest["upstream"]["schema_blob_sha"],
        )

        self.assertTrue(
            any(
                "response envelope drift for GET /panel/api/server/status" in item
                for item in errors
            ),
            errors,
        )

    def test_source_discovery_normalizes_dynamic_and_direct_routes(self):
        manifest, _, _ = self.load_fixture()
        routes = gate.discover_client_routes(ROOT, manifest["source_files"])

        self.assertIn(("GET", "/panel/api/inbounds/list"), routes)
        self.assertIn(("GET", "/panel/api/inbounds/list/slim"), routes)
        self.assertIn(("GET", "/panel/api/server/getDb"), routes)
        self.assertIn(("GET", "/panel/api/clients/get/tgId/{tgId}"), routes)
        self.assertIn(("GET", "/panel/api/clients/subLinks/{subId}"), routes)
        self.assertIn(("POST", "/panel/api/server/installXray/{version}"), routes)

    def test_getdb_binary_runtime_exception_is_explicit_and_unique(self):
        manifest, _, _ = self.load_fixture()
        weak = {
            (item["method"], item["path"])
            for item in manifest["endpoints"]
            if item.get("response_envelope", True) is False
        }
        exceptions = {
            (item["method"], item["path"])
            for item in manifest["documented_exceptions"]
        }

        self.assertEqual(
            weak,
            {("GET", "/panel/api/server/getDb")},
        )
        self.assertEqual(exceptions, weak)


if __name__ == "__main__":
    unittest.main()
