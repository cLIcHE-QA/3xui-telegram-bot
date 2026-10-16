"""Негативные проверки денежного ввода новых тарифов (#705)."""
from __future__ import annotations

import ast
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import unittest


def _load_parser():
    source = (Path(__file__).resolve().parents[1] / "catalog_admin.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_parse_price")
    module = ast.Module(body=[fn], type_ignores=[])
    ns = {"Decimal": Decimal, "InvalidOperation": InvalidOperation, "re": re}
    exec(compile(module, "catalog_admin.py", "exec"), ns)
    return ns["_parse_price"]


class NewPlanRubPriceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parse_price = staticmethod(_load_parser())

    def test_kopecks_without_rounding(self):
        for raw, expected in [("499", 49900), ("499.90 RUB", 49990), ("0", 0),
                              ("0,01", 1), ("200", 20000), ("540.00 RUB", 54000),
                              ("1020", 102000), ("1800", 180000)]:
            with self.subTest(raw=raw):
                self.assertEqual(self.parse_price(raw), (expected, "RUB"))

    def test_fail_closed_for_invalid_currency_or_precision(self):
        for raw in ["5 EUR", "5 USD", "5 XTR", "5 ABC", "1.234", "0.001", "1e2",
                    "NaN", "Infinity", "-1", "", "1 RUB extra", "1..2",
                    "0x10", "1 RUB USD", "100000001", ".5"]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.parse_price(raw)

    def test_legacy_default_currency_cannot_enable_new_eur(self):
        self.assertEqual(self.parse_price("7", "EUR"), (700, "RUB"))
        with self.assertRaises(ValueError):
            self.parse_price("7 EUR", "EUR")


if __name__ == "__main__":
    unittest.main()
