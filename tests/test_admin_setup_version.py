from __future__ import annotations

import unittest
from pathlib import Path

from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]
ADMIN_SETUP = ROOT / "docs" / "ADMIN_SETUP.md"


class AdminSetupReleaseVersionTests(unittest.TestCase):
    def test_canonical_install_flow_matches_app_version(self):
        doc = ADMIN_SETUP.read_text(encoding="utf-8")
        version = APP_VERSION
        tag = f"v{version}"

        self.assertIn(f"Guide ориентирован на release {tag}.", doc)
        self.assertIn(f"Для bot release `{tag}`", doc)
        self.assertIn(f"git checkout --detach {tag}", doc)
        self.assertIn("~~~text\n" + version + "\n~~~", doc)
        self.assertIn(f"3xui-host-control-bundle-{tag}.tar.gz", doc)
        self.assertIn(f"Git tag: {tag}", doc)
        self.assertIn(f"Bot version: {version}", doc)


if __name__ == "__main__":
    unittest.main()
