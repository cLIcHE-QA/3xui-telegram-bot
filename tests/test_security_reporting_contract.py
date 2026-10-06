from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SecurityReportingContractTests(unittest.TestCase):
    def test_security_policy_documents_supported_versions_and_private_reporting(self):
        text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("## Supported versions", text)
        self.assertIn("## Reporting a vulnerability", text)
        self.assertIn("Private Vulnerability Reporting", text)
        self.assertIn("Report a vulnerability", text)
        self.assertIn("No fixed SLA is promised", text)
        self.assertIn("Do **not** open a normal public issue", text)

    def test_private_vulnerability_report_form_exists_and_redacts_secrets(self):
        text = (
            ROOT / ".github" / "VULNERABILITY_REPORT.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("name: Private vulnerability report", text)
        self.assertIn("Affected version / commit", text)
        self.assertIn("Proof of concept / reproduction", text)
        self.assertIn("Do not paste live credentials", text)
        self.assertIn("Possible credential exposure", text)

    def test_public_issue_forms_redirect_security_reports(self):
        issue_dir = ROOT / ".github" / "ISSUE_TEMPLATE"
        for name in ("bug.yml", "feature.yml", "task.yml"):
            text = (issue_dir / name).read_text(encoding="utf-8")
            self.assertIn("Security vulnerability?", text)
            self.assertIn("Report a vulnerability", text)
            self.assertIn("Never paste credentials", text)

        config = (issue_dir / "config.yml").read_text(encoding="utf-8")
        self.assertIn("Security vulnerability — private reporting", config)
        self.assertIn("Не открывай public issue", config)


if __name__ == "__main__":
    unittest.main()
