from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from stars_invoice_ui import stars_invoice_title


class StarsInvoiceTitleTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_bot_display_name_instead_of_plan_name(self):
        bot = SimpleNamespace(me=AsyncMock(
            return_value=SimpleNamespace(full_name="КЛИШЕ VPN")
        ))
        self.assertEqual(await stars_invoice_title(bot), "КЛИШЕ VPN")
        bot.me.assert_awaited_once()

    async def test_long_name_is_limited_to_telegram_invoice_title(self):
        bot = SimpleNamespace(me=AsyncMock(
            return_value=SimpleNamespace(full_name="Б" * 40)
        ))
        self.assertEqual(await stars_invoice_title(bot), "Б" * 32)


class StarsInvoiceRoutingContractTests(unittest.TestCase):
    def test_both_native_stars_invoice_paths_use_bot_name(self):
        text = (Path(__file__).resolve().parents[1] / "client_access.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(text.count("title=await stars_invoice_title(call.bot),"), 2)
        self.assertNotIn("title=plan.name[:32],", text)
        self.assertIn('label=plan.name[:32]', text)


if __name__ == "__main__":
    unittest.main()
