"""rc.18.4: bounded HWID presentation regressions, без реальных identifiers."""
import unittest

from device_model_resolver import display_device_model
from device_presentation import recognized_vpn_app


class Rc184HwidRegressionTests(unittest.TestCase):
    def test_operator_cases(self):
        cases = (
            ("INCY/3.7.9/android Dalvik/2.1.0", "Incy"),
            ("INCY/3.8.8/windows 11 Dalvik/21.0.12+8-LTS", "Incy"),
            ("v2rayN/26.10.4 OneXray/26.10.4 (net.yuandev.onexray; build:467; ios)", "OneXray"),
            ("Karing/1.2.25.2802 platform/ios;mihomo/1.19.28;clash-verge;FLClash;"
             "mihomo.party/v2.0.0 (clash.meta);ClashMeta;v2ray;sing-box 1.13.0;"
             "NekoBox/Android/1.4.1 (Preferences)", "Karing"),
            ("Happ/1.2", "Happ"),
            ("V2Box 10.1.9/iOS 26.5.1", "V2Box"),
            ("v2rayNG/1.9.46", "v2rayNG"),
            ("sing-box/1.12.0", "sing-box"),
        )
        for ua, expected in cases:
            with self.subTest(ua=ua[:25]):
                self.assertEqual(recognized_vpn_app(ua), expected)

    def test_security_fail_closed(self):
        for ua in (
            "Dalvik/2.1.0", "okhttp/4.12.0", "Mozilla/5.0", "curl/8.0.1",
            "INCY/3.7.9/android Dalvik/2.1.0 token=secret",
            "v2rayN/26.10.4 OneXray/26.10.4 (net.yuandev.onexray; build:467; ios) extra",
            "Karing/1.2.25 platform/ios;token=private", "Happ/1.0\nInjected",
            "<b>Incy</b>/1.0", "Happ/1.0 http://bad.example",
            "Happ/" + "9" * 800,
        ):
            with self.subTest(ua=ua[:30]):
                self.assertEqual(recognized_vpn_app(ua), "")

    def test_device_fallbacks(self):
        for model, os_name, expected in (
            ("Google sdk_gphone16k_arm64", "Android 17", "Устройство Android"),
            ("sdk_gphone16k_arm64", "Android 17", "Устройство Android"),
            ("generic_x86_64", "Android 17", "Устройство Android"),
            ("emulator", "Android 17", "Устройство Android"),
            ("Pixel 9", "Android 17", "Pixel 9"),
            ("iPad Pro (12.9-inch) (3rd generation)", "macOS (Designed for iPad) 26.7", "Mac (модель не определена)"),
            ("iPad Pro (12.9-inch) (3rd generation)", "iPadOS 26.7", "iPad Pro (12.9-inch) (3rd generation)"),
            ("Unknown device", "Androidish", "Unknown device"),
            ("iPhone", "iOSFake", "iPhone"),
            ("iPad", "macOSfake", "iPad"),
            ("ThinkPad T14", "Windows 11", "ThinkPad T14"),
        ):
            with self.subTest(model=model, os=os_name):
                self.assertEqual(display_device_model(model, os_name), expected)


if __name__ == "__main__":
    unittest.main()
