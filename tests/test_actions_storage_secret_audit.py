from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load():
    scripts_dir = ROOT / "scripts"
    path = scripts_dir / "scan-github-actions-storage.py"
    inserted = str(scripts_dir) not in sys.path
    if inserted:
        sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("actions_storage_audit", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted:
            sys.path.remove(str(scripts_dir))


audit = _load()


class ActionsStorageAuditTests(unittest.TestCase):
    def test_scan_text_fingerprints_secret_value(self):
        value = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
        findings = audit._scan_text(f"TOKEN={value}", "run:1/log")
        self.assertTrue(findings)
        rendered = repr(findings)
        self.assertNotIn(value, rendered)

    def test_scan_zip_flags_sensitive_path_without_value(self):
        import io
        import zipfile

        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("nested/.env", "TOKEN=example-placeholder-secret-value")

        findings, coverage = audit._scan_zip(
            payload.getvalue(),
            source_prefix="artifact:1",
        )
        self.assertFalse(coverage)
        self.assertTrue(
            any(item["detector"] == "env-file" for item in findings)
        )
        self.assertNotIn("example-placeholder-secret-value", repr(findings))

    def test_aggregate_deduplicates_by_detector_and_fingerprint(self):
        findings = [
            {"detector": "private-ipv4", "fingerprint": "abc", "source": "a"},
            {"detector": "private-ipv4", "fingerprint": "abc", "source": "b"},
        ]
        aggregated = audit._aggregate(findings)
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(aggregated[0]["occurrences"], 2)


if __name__ == "__main__":
    unittest.main()
