"""#827: Karing upstream/truncated diagnostics, no real identifiers."""
import unittest
from pathlib import Path
from device_presentation import recognized_vpn_app
from device_model_resolver import display_device_model
from device_presentation import display_os

FULL = "Karing/1.2.25.2802 platform/ios;mihomo/1.19.28;clash-verge;FLClash;mihomo.party/v2.0.0 (clash.meta);ClashMeta;v2ray;sing-box 1.13.0;NekoBox/Android/1.4.1 (Preferences)"

REAL_FORMAT = FULL.replace(" (Preferences)", " (Prefer ClashMeta Format);HiddifyNext")

class KaringUserAgentTruncationTests(unittest.TestCase):
    def test_full_and_exact_160_cut(self):
        self.assertEqual(len(FULL), 167)
        self.assertEqual(FULL[:160][-6:], "(Prefe")
        self.assertEqual(recognized_vpn_app(FULL), "Karing")
        self.assertEqual(recognized_vpn_app(FULL[:160]), "Karing")

    def test_observed_191_character_karing_format(self):
        self.assertEqual(len(REAL_FORMAT), 191)
        self.assertEqual(REAL_FORMAT[:160], FULL[:160])
        self.assertEqual(recognized_vpn_app(REAL_FORMAT), "Karing")
        self.assertEqual(recognized_vpn_app(REAL_FORMAT.lower()), "Karing")

    def test_altered_or_secret_suffixes_remain_unrecognized(self):
        variants = (
            REAL_FORMAT + " token=secret",
            REAL_FORMAT + ";ExtraApp",
            REAL_FORMAT.replace("HiddifyNext", "Hiddify"),
            REAL_FORMAT.replace(";HiddifyNext", ""),
            REAL_FORMAT.replace("Prefer ClashMeta Format", "Prefer Other Format"),
            REAL_FORMAT.replace("ClashMeta;v2ray", "ClashMeta;extra;v2ray"),
            REAL_FORMAT.replace("NekoBox/Android", "NekoBox/iOS"),
            REAL_FORMAT + "\\nInjected",
        )
        for candidate in variants:
            with self.subTest(length=len(candidate), tail=candidate[-25:]):
                self.assertEqual(recognized_vpn_app(candidate), "")

    def test_fail_closed_noncanonical_tails(self):
        samples = (
            FULL[:159], FULL[:161], FULL[:160] + " ", FULL + " token=secret",
            FULL.replace("ClashMeta", "OtherName")[:160],
            FULL.replace("NekoBox/Android", "NekoBox/iOS")[:160],
            FULL[:160].replace("1.13.0", "1.13.a"),
            "Karing/1.2.25.2802 platform/ios;token=secret",
        )
        for raw in samples:
            with self.subTest(length=len(raw)):
                self.assertEqual(recognized_vpn_app(raw), "")

    def test_device_and_os_unchanged(self):
        self.assertEqual(display_device_model("Unknown device", "iOS", FULL[:160]), "Устройство iOS")
        self.assertEqual(display_os("iOS", "26.5.1"), "iOS 26.5.1")

    def test_admin_only_bounded_diagnostics(self):
        src = Path("advanced_users.py").read_text(encoding="utf-8")
        detail = src.split("async def user_device_detail(", 1)[1].split(
            'F.data.regexp(r"^admin:u:devdelask:', 1
        )[0]
        self.assertIn("len(raw_user_agent)", detail)
        self.assertIn("recognized_vpn_app(raw_user_agent)", detail)
        self.assertIn("[:160]", detail)
        self.assertIn("ua_preview_note", detail)
        self.assertIn("Распознано по полному User-Agent", detail)
        self.assertNotIn("delete_client_hwid(", detail)
