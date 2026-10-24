"""D1a: validate exact structural roundtrip against synthetic fixtures.

To test the operator's private export locally:
python -m unittest tests.test_subscription_page_config
No customer URLs or raw SVG are committed.
"""
import copy
import json
import unittest

from subscription_page_config import (
    InvalidSubscriptionConfig, config_summary, parse_config, serialize_config,
)

LOCALES = ["en", "ru", "zh", "fa", "fr"]


def multilingual(label):
    return {code: f"{label}-{code}" for code in LOCALES}


def fixture():
    return {
        "locales": LOCALES,
        "version": "1",
        "uiConfig": {"subscriptionInfoBlockType": "expanded", "installationGuidesBlockType": "cards"},
        "platforms": {
            "ios": {
                "apps": [{
                    "name": "Example client",
                    "featured": True,
                    "svgIconKey": "Example",
                    "blocks": [
                        {"title": multilingual("Install"), "description": multilingual("Instructions"),
                         "svgIconKey": "Download", "svgIconColor": "cyan",
                         "buttons": [{"link": "https://example.invalid/install", "type": "external",
                                      "text": multilingual("Download"), "svgIconKey": "ExternalLink"}]},
                        {"title": multilingual("Import"), "description": multilingual("Import details"),
                         "buttons": [{"link": "client://import/{{SUBSCRIPTION_LINK}}", "type": "subscriptionLink",
                                      "text": multilingual("Add"), "svgIconKey": "Plus"}]},
                    ],
                }]
            }
        },
        "svgLibrary": {"Example": "<svg xmlns=\"http://www.w3.org/2000/svg\"/>"},
        "baseSettings": {
            "metaTitle": "Example", "metaDescription": "Example",
            "showConnectionKeys": False, "hideGetLinkButton": False,
        },
        "baseTranslations": {"installationGuideHeader": multilingual("Guide")},
        "brandingSettings": {"title": "Example", "logoUrl": "", "supportUrl": ""},
    }


class TestSubscriptionPageConfig(unittest.TestCase):
    def test_roundtrip_preserves_all_fields_strings_and_order(self):
        original = fixture()
        imported = parse_config(json.dumps(original, ensure_ascii=False))
        self.assertEqual(imported, original)
        self.assertEqual(list(imported), list(original))
        self.assertEqual(parse_config(serialize_config(imported)), original)
        self.assertEqual(imported["platforms"]["ios"]["apps"][0]["blocks"][1]["buttons"][0]["link"],
                         "client://import/{{SUBSCRIPTION_LINK}}")

    def test_source_is_not_modified(self):
        original = fixture()
        saved = copy.deepcopy(original)
        parsed = parse_config(json.dumps(original))
        parsed["baseSettings"]["hideGetLinkButton"] = True
        self.assertEqual(original, saved)

    def test_stats_no_secret_strings(self):
        info = config_summary(parse_config(json.dumps(fixture())))
        self.assertEqual(info, {"languages": 5, "platforms": 1, "app_slots": 1,
                                "unique_apps": 1, "blocks": 2, "buttons": 2, "svg_icons": 1})
        self.assertNotIn("client://", json.dumps(info))

    def test_invalid_version_and_shape_rejected(self):
        cfg = fixture()
        cfg["version"] = "3"
        with self.assertRaises(InvalidSubscriptionConfig):
            parse_config(json.dumps(cfg))
        cfg = fixture()
        cfg["platforms"]["ios"]["apps"][0]["blocks"][0]["title"].pop("ru")
        with self.assertRaises(InvalidSubscriptionConfig):
            parse_config(json.dumps(cfg))

    def test_private_operator_export_when_available(self):
        """Locally supply OPERATOR_SUBPAGE_JSON; never commit or print contents."""
        import os
        import hashlib
        from pathlib import Path
        source_path = os.environ.get("OPERATOR_SUBPAGE_JSON")
        if not source_path:
            self.skipTest("Private operator export unavailable in CI")
        raw = Path(source_path).read_bytes()
        expected_sha256 = "acc2a517287832fcf7e42d7482eceea55bdc2b6b670a6e5b3bab23680f323244"
        self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_sha256)
        original = json.loads(raw)
        result = parse_config(raw)
        self.assertEqual(result, original)
        self.assertEqual(parse_config(serialize_config(result)), original)
        self.assertEqual(config_summary(result), {
            "languages": 5, "platforms": 7, "app_slots": 24,
            "unique_apps": 10, "blocks": 92, "buttons": 75, "svg_icons": 38
        })

    def test_file_size_limit(self):
        with self.assertRaises(InvalidSubscriptionConfig):
            parse_config(b"x" * (1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main()
