"""Safety tests for the operator-only QA #352 Telegram delivery runner."""
from __future__ import annotations
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qa352_telegram_delivery.py"
spec = importlib.util.spec_from_file_location("qa352_delivery_test_module", SCRIPT)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


class QATelegramDeliveryContract(unittest.TestCase):
    def test_01_exact_four_sanitized_messages(self):
        messages = [qa.message_for_step(n) for n in range(1, 5)]
        self.assertEqual(len(set(messages)), 4)
        self.assertTrue(all("СИНТЕТИЧЕСКОЕ" in m and "НЕ АВАРИЯ" in m for m in messages))
        self.assertIn("Новая ошибка", messages[0])
        self.assertIn("Повторное напоминание", messages[1])
        self.assertIn("Исходная ошибка", messages[3])
        self.assertIn("Восстановлено", messages[3])
        self.assertRaises(qa.SafetyError, qa.message_for_step, 5)

    def test_02_prevent_prod_token_and_bad_username(self):
        with patch.dict(os.environ, {
            "BOT_TOKEN": "same", "QA352_BOT_TOKEN": "same",
            "QA352_EXPECTED_BOT_USERNAME": "some_qa_bot",
        }):
            self.assertRaises(qa.SafetyError, qa._token_and_expected_username)
        with patch.dict(os.environ, {
            "BOT_TOKEN": "different", "QA352_BOT_TOKEN": "qa",
            "QA352_EXPECTED_BOT_USERNAME": "normal_bot",
        }):
            self.assertRaises(qa.SafetyError, qa._token_and_expected_username)

    def test_03_enroll_only_private_one_start(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(qa, "STATE_DIR", Path(temp) / "private"), \
                 patch.object(qa, "_token_and_expected_username", return_value=("secret", "qa_test_bot")), \
                 patch.object(qa, "_identified_bot", return_value={"id": 99, "username": "qa_test_bot"}), \
                 patch.object(qa, "telegram_call") as api:
                api.side_effect = [
                    {"url": ""},
                    [{"message": {
                        "chat": {"id": 10001, "type": "private"},
                        "from": {"id": 10001, "is_bot": False},
                        "text": "/start",
                    }}],
                ]
                qa.enroll(qa.ENROLL_PHRASE)
                self.assertEqual(api.call_count, 2)
                with qa._open_store() as conn:
                    self.assertEqual(conn.execute("SELECT phase FROM qa_session").fetchone()[0], "confirmed")

    def test_04_uncertain_send_not_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(qa, "STATE_DIR", Path(temp) / "private"), \
                 patch.object(qa, "_token_and_expected_username", return_value=("secret", "qa_test_bot")), \
                 patch.object(qa, "_identified_bot", return_value={"id": 99, "username": "qa_test_bot"}):
                with qa._open_store() as conn:
                    conn.execute(
                        "INSERT INTO qa_session VALUES (1,?,?,?,?,?,?,?)",
                        (99, "qa_test_bot", 10001, 0, "confirmed", None, int(qa.time.time()) + 600),
                    )
                    conn.commit()
                with patch.object(qa, "telegram_call", side_effect=qa.SafetyError("unknown")) as api:
                    self.assertRaises(qa.SafetyError, qa.send_one, 1, qa.SEND_PHRASE)
                    self.assertRaises(qa.SafetyError, qa.send_one, 1, qa.SEND_PHRASE)
                    self.assertEqual(api.call_count, 1)
                with qa._open_store() as conn:
                    row=conn.execute("SELECT step, phase FROM qa_session").fetchone()
                    self.assertEqual(tuple(row), (1, "unknown"))

    def test_05_send_accepted_requires_operator_ack(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(qa, "STATE_DIR", Path(temp) / "private"), \
                 patch.object(qa, "_token_and_expected_username", return_value=("secret", "qa_test_bot")), \
                 patch.object(qa, "_identified_bot", return_value={"id": 99, "username": "qa_test_bot"}):
                with qa._open_store() as conn:
                    conn.execute(
                        "INSERT INTO qa_session VALUES (1,?,?,?,?,?,?,?)",
                        (99, "qa_test_bot", 10001, 0, "confirmed", None, int(qa.time.time()) + 600),
                    )
                    conn.commit()
                with patch.object(qa, "telegram_call", return_value={
                    "message_id": 123, "chat": {"id": 10001, "type": "private"},
                    "from": {"id": 99},
                }) as api:
                    qa.send_one(1, qa.SEND_PHRASE)
                    self.assertRaises(qa.SafetyError, qa.send_one, 2, qa.SEND_PHRASE)
                    qa.confirm_observed(1, "YES")
                    self.assertEqual(api.call_count, 1)


if __name__ == "__main__":
    unittest.main()
