from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SupplyChainBaselineTests(unittest.TestCase):
    def test_dockerfile_uses_pinned_base_and_hashed_lock(self):
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertRegex(
            text.splitlines()[0],
            r"^FROM python:3\.12-slim@sha256:[0-9a-f]{64}$",
        )
        self.assertIn("COPY requirements.lock .", text)
        self.assertIn("pip install --no-cache-dir --require-hashes -r requirements.lock", text)
        self.assertNotIn("pip install --no-cache-dir -r requirements.txt", text)

    def test_lock_contains_exact_versions_and_hashes(self):
        text = (ROOT / "requirements.lock").read_text(encoding="utf-8")
        self.assertIn("aiogram==", text)
        self.assertIn("--hash=sha256:", text)
        self.assertNotRegex(text, r"(?m)^[A-Za-z0-9_.-]+[<>~]=")

    def test_all_third_party_actions_are_full_sha_pinned(self):
        workflow_dir = ROOT / ".github" / "workflows"
        uses_re = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
        full_sha_re = re.compile(r"^[^@]+@[0-9a-f]{40}$")
        for path in workflow_dir.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            for ref in uses_re.findall(text):
                if ref.startswith("./"):
                    continue
                self.assertRegex(ref, full_sha_re, f"{path}: mutable action ref {ref}")

    def test_supply_chain_audit_is_read_only_and_pinned(self):
        text = (
            ROOT / ".github" / "workflows" / "supply-chain-audit.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("trivy_0.75.0_Linux-64bit.tar.gz", text)
        self.assertIn(
            "c6e65abddb348e25f10549df887045629cf28cc72453cd1c63acb717316b3f3f",
            text,
        )
        self.assertIn("--require-hashes -r requirements.lock", text)
        self.assertIn("--format cyclonedx", text)
        self.assertIn("--severity HIGH,CRITICAL", text)
        self.assertIn("--ignore-unfixed", text)
        self.assertIn("Gate actionable HIGH/CRITICAL vulnerabilities", text)
        self.assertNotIn("contents: write", text)

    def test_base_digest_file_matches_dockerfile(self):
        base = (ROOT / "supply-chain" / "base-image.txt").read_text(encoding="utf-8").strip()
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(docker, "FROM " + base)


if __name__ == "__main__":
    unittest.main()
