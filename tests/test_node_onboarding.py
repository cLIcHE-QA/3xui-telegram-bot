from __future__ import annotations

import unittest

from node_onboarding import AddNodeStates, node_mutation_payload, parse_node_url


class NodeOnboardingTests(unittest.TestCase):
    def test_url_defaults_to_https_and_normalizes_panel_suffix(self):
        parsed = parse_node_url("fi.example.invalid:2053/base/panel/")
        self.assertEqual(
            parsed,
            {
                "scheme": "https",
                "address": "fi.example.invalid",
                "port": 2053,
                "basePath": "/base/",
            },
        )

    def test_url_preserves_http_and_default_port(self):
        parsed = parse_node_url("http://node.example.invalid")
        self.assertEqual(parsed["scheme"], "http")
        self.assertEqual(parsed["port"], 80)
        self.assertEqual(parsed["basePath"], "/")

    def test_url_rejects_empty_credentials_and_invalid_scheme(self):
        for raw in (
            "",
            "ftp://node.example.invalid",
            "https://user:secret@node.example.invalid",
            "https://node.example.invalid:not-a-port",
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    parse_node_url(raw)

    def test_mutation_payload_keeps_fixed_safe_defaults(self):
        payload = node_mutation_payload(
            {
                "name": "Finland",
                "scheme": "https",
                "address": "fi.example.invalid",
                "port": 2053,
                "basePath": "/base/",
                "apiToken": "token-value",
            }
        )
        self.assertEqual(payload["id"], 0)
        self.assertEqual(payload["name"], "Finland")
        self.assertEqual(payload["tlsVerifyMode"], "verify")
        self.assertTrue(payload["enable"])
        self.assertFalse(payload["allowPrivateAddress"])
        self.assertEqual(payload["inboundSyncMode"], "all")
        self.assertEqual(payload["inboundTags"], [])
        self.assertFalse(payload["clearApiToken"])

    def test_mutation_payload_preserves_explicit_tls_mode(self):
        payload = node_mutation_payload(
            {
                "name": "Finland",
                "scheme": "https",
                "address": "fi.example.invalid",
                "port": 443,
                "basePath": "/",
                "apiToken": "token-value",
                "tlsVerifyMode": "skip",
            }
        )
        self.assertEqual(payload["tlsVerifyMode"], "skip")

    def test_add_node_states_remain_distinct(self):
        states = {
            AddNodeStates.name.state,
            AddNodeStates.url.state,
            AddNodeStates.token.state,
            AddNodeStates.review.state,
        }
        self.assertEqual(len(states), 4)


if __name__ == "__main__":
    unittest.main()
