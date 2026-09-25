from __future__ import annotations

import unittest
from types import SimpleNamespace

from inbound_policy import is_managed_inbound


def settings(**overrides):
    values = {
        "inbound_ids": (),
        "ignored_protocols": (),
        "ignored_tags": (),
        "allowed_ports": (),
        "allowed_protocols": (),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def inbound(**overrides):
    values = {
        "id": 7,
        "protocol": "vless",
        "tag": "public",
        "port": 443,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class InboundPolicyTests(unittest.TestCase):
    def test_default_allows_regular_inbound(self):
        self.assertTrue(is_managed_inbound(settings(), inbound()))

    def test_ignored_protocol_and_tag_are_rejected(self):
        self.assertFalse(
            is_managed_inbound(
                settings(ignored_protocols=("dokodemo-door",)),
                inbound(protocol="dokodemo-door"),
            )
        )
        self.assertFalse(
            is_managed_inbound(
                settings(ignored_tags=("internal",)),
                inbound(tag="internal"),
            )
        )
        self.assertFalse(is_managed_inbound(settings(), inbound(tag="api")))

    def test_explicit_allowlists_are_enforced(self):
        self.assertFalse(
            is_managed_inbound(settings(inbound_ids=(8,)), inbound(id=7))
        )
        self.assertFalse(
            is_managed_inbound(settings(allowed_ports=(8443,)), inbound(port=443))
        )
        self.assertFalse(
            is_managed_inbound(
                settings(allowed_protocols=("trojan",)),
                inbound(protocol="vless"),
            )
        )
        self.assertTrue(
            is_managed_inbound(
                settings(
                    inbound_ids=(7,),
                    allowed_ports=(443,),
                    allowed_protocols=("vless",),
                ),
                inbound(),
            )
        )


if __name__ == "__main__":
    unittest.main()
