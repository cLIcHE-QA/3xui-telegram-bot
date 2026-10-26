"""#887 D3h: изолированный приём evidence без device-аттестации в CI."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from subscription_page_import_attestations import (
    MANIFEST_PATH, inspect_d3h_staging_readiness, load_reviewed_clients,
    reviewed_clients_from_manifest,
)

SHA = "a" * 40
VERSION = "2.6.4"
BASE = {
    "schema": 1,
    "issue": "#887",
    "candidates": [
        {"platform": "ios", "clientId": "incy", "clientVersion": VERSION, "priorIssue": "#473"},
        {"platform": "android", "clientId": "incy", "clientVersion": VERSION, "priorIssue": "#473"},
        {"platform": "ios", "clientId": "happ", "clientVersion": None, "priorIssue": "#473"},
    ],
    "reviewed": [],
}
REVIEW = {
    "platform": "ios", "clientId": "incy", "clientVersion": VERSION,
    "reviewIssue": "#887", "allowCopy": True, "allowQr": True,
    "evidence": {
        "auditPath": "docs/audits/2026-10-26-887-d3h-fixture.md",
        "buildSha": SHA, "testedAt": "2026-10-26T18:00:00+00:00",
        "deviceModel": "Synthetic iPhone", "osVersion": "synthetic-26.0",
        "clientVersion": VERSION, "clientBuild": "Synthetic app build 123", "browserVersion": "Synthetic Safari 1.0",
        "telegramVersion": "Synthetic Telegram 1.0",
        "native": {"copy": "PASS", "qr": "PASS"},
        "webview": {"copy": "PASS", "qr": "PASS"},
        "privacy": {
            "ownerDenied": "PASS", "replayDenied": "PASS",
            "cacheNoStore": "PASS", "logsRedacted": "PASS",
        },
    },
}


class D3hEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        audit = self.root / REVIEW["evidence"]["auditPath"]
        audit.parent.mkdir(parents=True)
        audit.write_text(
            "# Synthetic fixture — не аттестация устройства\n"
            "<!-- audit-schema: 1 -->\n"
            "- **Связанные Issues:** #887\n"
            f"- **Версия и immutable tag/SHA:** {SHA}\n",
            encoding="utf-8",
        )

    def with_review(self):
        record = copy.deepcopy(BASE)
        record["reviewed"].append(copy.deepcopy(REVIEW))
        return record

    def rejects(self, record):
        with self.assertRaises(ValueError):
            reviewed_clients_from_manifest(record, root=self.root)

    def test_repository_shipping_defaults_remain_inert(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(load_reviewed_clients(root=root), ())
        document = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
        self.assertEqual(document["reviewed"], [])
        self.assertEqual(len(document["candidates"]), 7)
        frontend = (root / "web/subscription-page/src/reviewedCapabilities.ts").read_text(encoding="utf-8")
        screen = (root / "web/subscription-page/src/main.tsx").read_text(encoding="utf-8")
        backend = (root / "subscription_page_import_http.py").read_text(encoding="utf-8")
        runtime = (root / "app_runtime.py").read_text(encoding="utf-8")
        self.assertIn("Object.freeze([])", frontend)
        self.assertIn("pilotEnabled={false}", screen)
        self.assertIn("clientVersion=\"\"", screen)
        self.assertIn("delivery_enabled: bool = False", backend)
        self.assertIn("reviewed_clients: tuple[ReviewedImportClient, ...] = ()", backend)
        self.assertNotIn("subscription_page_import_attestations", runtime)

    def isolated_source_tree(self):
        repository = Path(__file__).resolve().parents[1]
        isolated = self.root / "readonly-contracts"
        contract_paths = (
            MANIFEST_PATH,
            "web/subscription-page/src/main.tsx",
            "web/subscription-page/src/reviewedCapabilities.ts",
            "subscription_page_import_http.py",
            "subscription_page_staging.py",
            "subscription_page_pilot_wiring.py",
            "app_runtime.py",
            "deploy/subpage-staging/nginx-d2d-staging.conf.example",
        )
        for relative in contract_paths:
            destination = isolated / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repository / relative, destination)
        return isolated

    def test_d3h_staging_readiness_is_offline_and_explicitly_blocked(self):
        project = self.isolated_source_tree()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            report = inspect_d3h_staging_readiness(root=project)
        self.assertEqual(report, {
            "schema": 1, "scope": "D3h", "status": "BLOCKED",
            "candidate_count": 7, "reviewed_count": 0,
            "device_evidence": "PENDING",
            "staging_import_routes": "NOT_WIRED",
            "frontend_import": "OFF", "server_delivery": "OFF",
            "live_requests_sent": 0,
            "next_gate": "isolated_staging_review_and_physical_device_smoke",
        })
        self.assertNotIn("subscriptionUrl", json.dumps(report))

    def test_d3h_staging_drift_is_rejected_without_network(self):
        scenarios = {
            "frontend-gate": (
                "web/subscription-page/src/main.tsx",
                "pilotEnabled={false}", "pilotEnabled={true}",
            ),
            "client-version": (
                "web/subscription-page/src/main.tsx",
                'clientVersion=""', 'clientVersion="2.6.4"',
            ),
            "trusted-capabilities": (
                "web/subscription-page/src/reviewedCapabilities.ts",
                "Object.freeze([])", 'Object.freeze([{"platform":"ios"}])',
            ),
            "backend-gate": (
                "subscription_page_import_http.py",
                "delivery_enabled: bool = False", "delivery_enabled: bool = True",
            ),
            "staging-wiring": (
                "subscription_page_staging.py",
                "#887 D2d:", "#887 D2d: subscription_page_import_http",
            ),
            "runtime-wiring": (
                "app_runtime.py",
                "import asyncio",
                "import asyncio\n# subscription_page_import_attestations",
            ),
            "ingress-route": (
                "deploy/subpage-staging/nginx-d2d-staging.conf.example",
                "location / {", "location = /api/subpage/v1/import/preflight/deliver { return 200; }\n    location / {",
            ),
        }
        for name, (relative, old, new) in scenarios.items():
            with self.subTest(name=name):
                project = self.isolated_source_tree()
                target = project / relative
                original = target.read_text(encoding="utf-8")
                self.assertIn(old, original)
                target.write_text(original.replace(old, new, 1), encoding="utf-8")
                with patch("socket.socket", side_effect=AssertionError("network forbidden")):
                    with self.assertRaises(ValueError):
                        inspect_d3h_staging_readiness(root=project)

    def test_d3h_readiness_missing_contract_or_bad_manifest_is_blocked(self):
        project = self.isolated_source_tree()
        (project / "subscription_page_pilot_wiring.py").unlink()
        with self.assertRaises(ValueError):
            inspect_d3h_staging_readiness(root=project)
        project = self.isolated_source_tree()
        (project / MANIFEST_PATH).write_text("not-json", encoding="utf-8")
        with self.assertRaises(ValueError):
            inspect_d3h_staging_readiness(root=project)

    def test_empty_shipping_reviewed_registry_does_not_promote_candidates(self):
        self.assertEqual(reviewed_clients_from_manifest(BASE, root=self.root), ())
        manifest = self.root / MANIFEST_PATH
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps(BASE), encoding="utf-8")
        self.assertEqual(load_reviewed_clients(root=self.root), ())
        # A strict negative fixture: no method is authorized by a prior Telegram smoke.
        self.assertEqual(len(BASE["candidates"]), 3)
        self.assertEqual(len(BASE["reviewed"]), 0)

    def test_synthetic_complete_evidence_only_compiles_offline_tuple(self):
        approved = reviewed_clients_from_manifest(self.with_review(), root=self.root)
        self.assertEqual(len(approved), 1)
        self.assertEqual(
            (approved[0].platform, approved[0].client_id, approved[0].version,
             approved[0].allow_copy, approved[0].allow_qr),
            ("ios", "incy", VERSION, True, True),
        )
        # This return value is not wired into the URL-delivery app or the frontend.

    def test_methods_are_independent_and_both_contexts_are_required(self):
        for context in ("native", "webview"):
            for method in ("copy", "qr"):
                record = self.with_review()
                record["reviewed"][0]["evidence"][context][method] = "PENDING"
                self.rejects(record)
        for allow, method in (("allowCopy", "copy"), ("allowQr", "qr")):
            record = self.with_review()
            record["reviewed"][0][allow] = False
            for context in ("native", "webview"):
                record["reviewed"][0]["evidence"][context][method] = "FAIL"
            approved = reviewed_clients_from_manifest(record, root=self.root)
            self.assertEqual(getattr(approved[0], "allow_copy" if method == "copy" else "allow_qr"), False)
        record = self.with_review()
        record["reviewed"][0].update({"allowCopy": False, "allowQr": False})
        self.rejects(record)

    def test_unsupported_client_platform_version_and_duplicates_fail_closed(self):
        changes = (
            ("clientVersion", "2.6.5"), ("clientVersion", "../bad"),
            ("clientVersion", None), ("platform", "macos"),
            ("platform", "windows"), ("clientId", "unknown"),
            ("reviewIssue", "#999"), ("allowCopy", "yes"),
        )
        for field, value in changes:
            record = self.with_review()
            record["reviewed"][0][field] = value
            with self.subTest(field=field, value=value):
                self.rejects(record)
        # Android/Incy — известный кандидат, но всё ещё только synthetic fixture.
        record = self.with_review()
        record["reviewed"][0]["platform"] = "android"
        self.assertEqual(
            reviewed_clients_from_manifest(record, root=self.root)[0].platform, "android",
        )
        record = self.with_review()
        record["reviewed"] *= 2
        self.rejects(record)
        record = self.with_review()
        record["candidates"].append(copy.deepcopy(record["candidates"][0]))
        self.rejects(record)
        record = self.with_review()
        record["reviewed"][0]["clientVersion"] = "1.0.0"
        self.rejects(record)

    def test_missing_bad_or_mismatched_physical_evidence_fails_closed(self):
        fields = {
            "buildSha": "short", "testedAt": "2026-10-26T12:00:00",
            "clientVersion": "2.7.0", "deviceModel": "",
            "osVersion": None, "browserVersion": "", "telegramVersion": "",
            "auditPath": "../../private.txt",
        }
        for field, value in fields.items():
            record = self.with_review()
            record["reviewed"][0]["evidence"][field] = value
            with self.subTest(field=field):
                self.rejects(record)
        for status in ("PENDING", "FAIL", "BLOCKED", "pass", True):
            record = self.with_review()
            record["reviewed"][0]["evidence"]["privacy"]["ownerDenied"] = status
            with self.subTest(status=status):
                self.rejects(record)
        record = self.with_review()
        del record["reviewed"][0]["evidence"]["privacy"]["logsRedacted"]
        self.rejects(record)
        record = self.with_review()
        record["reviewed"][0]["evidence"]["unexpected"] = "PASS"
        self.rejects(record)

    def test_audit_must_exist_and_contain_reviewed_sha_and_issue(self):
        record = self.with_review()
        audit = self.root / REVIEW["evidence"]["auditPath"]
        for content in ("", "#887 " + SHA, "<!-- audit-schema: 1 -->\n" + SHA,
                        "<!-- audit-schema: 1 -->\n#887\n"):
            audit.write_text(content, encoding="utf-8")
            self.rejects(record)
        audit.unlink()
        self.rejects(record)

    def test_malformed_manifest_and_failed_loading_are_rejected(self):
        for change in ({"schema": True}, {"schema": 2}, {"issue": "#473"},
                       {"reviewed": {}}, {"candidates": []}):
            record = copy.deepcopy(BASE)
            record.update(change)
            if change == {"candidates": []}:
                record["reviewed"] = [copy.deepcopy(REVIEW)]
            self.rejects(record)
        self.rejects({"schema": 1})
        with self.assertRaises(ValueError):
            load_reviewed_clients(root=self.root)
        path = self.root / MANIFEST_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{invalid json", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_reviewed_clients(root=self.root)


if __name__ == "__main__":
    unittest.main()
