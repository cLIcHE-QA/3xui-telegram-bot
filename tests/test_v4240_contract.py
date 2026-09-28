from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V4240ReleaseContractTests(unittest.TestCase):
    def test_roadmap_has_canonical_v4240_contract(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        start = roadmap.index("##### v4.24.0 — Мониторинг сайтов и web diagnostics")
        end = roadmap.index("##### v4.25.0 — User Management", start)
        section = roadmap[start:end]

        for needle in (
            "vladpak1/packbot",
            "3c4a5bb29626f8b3e28056bd52cd94fdce9f3c1a",
            "🌐 Мониторинг сайтов",
            "website_monitoring.view",
            "website_monitoring.manage",
            "website_monitoring.admin",
            "website_monitors",
            "website_monitor_watchers",
            "website_incidents",
            "unknown | up | suspect | down",
            "10 минут",
            "3 минуты",
            "2 секунды",
            "5 секунд",
            "redirects: не более **5**",
            "обычный response body: не более **1 MiB**",
            "sitemap document: не более **2 MiB**",
            "sitemap documents за одну операцию: не более **10**",
            "URLs из sitemap: не более **5000**",
            "PackBot parity matrix",
            "screenshots/headless browser",
        ):
            self.assertIn(needle, section)

    def test_packbot_attribution_is_pinned_and_complete(self):
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("## PackBot", notices)
        self.assertIn("https://github.com/vladpak1/packbot", notices)
        self.assertIn(
            "Reviewed revision: `3c4a5bb29626f8b3e28056bd52cd94fdce9f3c1a`",
            notices,
        )
        self.assertIn("License: MIT", notices)
        self.assertIn("Copyright (c) 2023 vladpak1", notices)
        self.assertIn(
            "Permission is hereby granted, free of charge, to any person obtaining a copy",
            notices,
        )

    def test_contract_keeps_v4240_inside_admin_monitoring(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        start = roadmap.index("##### v4.24.0 — Мониторинг сайтов и web diagnostics")
        end = roadmap.index("##### v4.25.0 — User Management", start)
        section = roadmap[start:end]

        self.assertIn("scope относится только к `/admin → Мониторинг`", section)
        self.assertIn("публичный `/start` и Client Portal не расширяются", section)
        self.assertIn("PHP/Composer/MySQL не становятся production dependencies", section)
        self.assertIn("PackBot не запускается как sidecar/service", section)


if __name__ == "__main__":
    unittest.main()
