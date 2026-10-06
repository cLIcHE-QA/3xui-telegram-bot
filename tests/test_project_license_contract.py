from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectLicenseContractTests(unittest.TestCase):
    def test_apache_2_license_is_canonical(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Apache License", text)
        self.assertIn("Version 2.0, January 2004", text)
        self.assertIn("TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION", text)
        self.assertIn("END OF TERMS AND CONDITIONS", text)

    def test_readme_and_third_party_notices_reference_project_license(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("## Лицензия", readme)
        self.assertIn("Apache License 2.0", readme)
        self.assertIn("[LICENSE](LICENSE)", readme)
        self.assertIn("Project-authored code is licensed under the Apache License 2.0", notices)
        self.assertIn("## Cheburcheck", notices)
        self.assertIn("## PackBot", notices)

    def test_a009_review_is_recorded(self):
        text = (
            ROOT / "docs" / "audits" / "v4-a009-license-review-2026-10-06.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Apache License 2.0", text)
        self.assertIn("MPL-2.0", text)
        self.assertIn("prebuilt container images", text)


if __name__ == "__main__":
    unittest.main()
