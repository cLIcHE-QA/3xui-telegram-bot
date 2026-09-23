from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from config import _load_host_control_targets


class HostControlConfigTests(unittest.TestCase):
    def load(self, values):
        base = {
            "HOST_CONTROL_TARGETS": "MASTER,FI",
            "HOST_CONTROL_MASTER_NAME": "Master",
            "HOST_CONTROL_MASTER_HOST_ID": "master",
            "HOST_CONTROL_MASTER_URL": "http://172.19.0.1:18182",
            "HOST_CONTROL_MASTER_TOKEN": "m" * 43,
            "HOST_CONTROL_MASTER_VERIFY_TLS": "true",
            "HOST_CONTROL_FI_NAME": "Finland",
            "HOST_CONTROL_FI_HOST_ID": "fi",
            "HOST_CONTROL_FI_URL": "https://fi-host-control.example.invalid",
            "HOST_CONTROL_FI_TOKEN": "f" * 43,
            "HOST_CONTROL_FI_VERIFY_TLS": "true",
        }
        base.update(values)
        with patch.dict(os.environ, base, clear=True):
            return _load_host_control_targets()

    def test_private_http_master_and_verified_https_node_are_allowed(self):
        targets = self.load({})
        self.assertEqual([t.key for t in targets], ["MASTER", "FI"])
        self.assertEqual(targets[0].host_id, "master")
        self.assertTrue(targets[1].verify_tls)

    def test_public_plain_http_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.load({"HOST_CONTROL_FI_URL": "http://203.0.113.10:18181"})

    def test_https_without_verification_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.load({"HOST_CONTROL_FI_VERIFY_TLS": "false"})

    def test_url_credentials_are_rejected(self):
        with self.assertRaises(RuntimeError):
            self.load({"HOST_CONTROL_FI_URL": "https://user:pass@example.invalid"})

    def test_duplicate_host_id_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.load({"HOST_CONTROL_FI_HOST_ID": "master"})

    def test_short_token_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.load({"HOST_CONTROL_FI_TOKEN": "short"})

    def test_tokens_must_be_unique_per_target(self):
        with self.assertRaises(RuntimeError):
            self.load({"HOST_CONTROL_FI_TOKEN": "m" * 43})

    def test_incomplete_target_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.load({"HOST_CONTROL_FI_URL": ""})


if __name__ == "__main__":
    unittest.main()
