from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _load("secret_audit_common", ROOT / "scripts" / "secret_audit_common.py")
sanitize = _load("sanitize_gitleaks_report", ROOT / "scripts" / "sanitize-gitleaks-report.py")


class SecretAuditTests(unittest.TestCase):
    def test_high_confidence_detector_finds_secret_without_emitting_value(self):
        value = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
        findings = list(common.scan_high_confidence(f"TOKEN={value}"))
        self.assertTrue(any(detector == "telegram-bot-token" for detector, _ in findings))
        self.assertTrue(all(value not in fingerprint for _, fingerprint in findings))

    def test_placeholder_is_ignored(self):
        findings = list(common.scan_high_confidence("token=example-placeholder-secret-value"))
        self.assertEqual(findings, [])

    def test_private_ip_is_fingerprinted(self):
        findings = list(common.scan_sensitive_metadata("host=10.20.30.40"))
        self.assertEqual(findings[0][0], "private-ipv4")
        self.assertNotIn("10.20.30.40", findings[0][1])

    def test_sensitive_paths_cover_env_db_and_backup(self):
        self.assertEqual(common.sensitive_path_reason(".env"), "env-file")
        self.assertEqual(common.sensitive_path_reason("data/bot.sqlite3"), "sensitive-file")
        self.assertEqual(common.sensitive_path_reason("foo/full-backup.tar.gz"), "backup-archive")
        self.assertIsNone(common.sensitive_path_reason(".env.example"))

    def test_gitleaks_sanitizer_drops_secret_fields(self):
        source = [{
            "RuleID": "generic-api-key",
            "Description": "example",
            "File": "app.py",
            "Commit": "a" * 40,
            "StartLine": 12,
            "Secret": "SUPER-SECRET-VALUE",
            "Match": "token=SUPER-SECRET-VALUE",
            "Fingerprint": "fp",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "raw.json"
            dst = Path(tmp) / "safe.json"
            src.write_text(json.dumps(source), encoding="utf-8")
            count = sanitize.sanitize(src, dst)
            self.assertEqual(count, 1)
            output = dst.read_text(encoding="utf-8")
            self.assertNotIn("SUPER-SECRET-VALUE", output)
            self.assertNotIn('"Secret"', output)
            self.assertNotIn('"Match"', output)
            self.assertIn('"RuleID"', output)


if __name__ == "__main__":
    unittest.main()
