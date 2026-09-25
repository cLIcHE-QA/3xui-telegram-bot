from __future__ import annotations


def is_managed_inbound(settings, inbound) -> bool:
    exact_ids = set(settings.inbound_ids)
    if inbound.protocol in set(settings.ignored_protocols):
        return False
    if (
        inbound.tag.lower() in set(settings.ignored_tags)
        or inbound.tag.lower().startswith("api")
    ):
        return False
    if exact_ids and inbound.id not in exact_ids:
        return False
    if settings.allowed_ports and inbound.port not in set(settings.allowed_ports):
        return False
    if (
        settings.allowed_protocols
        and inbound.protocol not in set(settings.allowed_protocols)
    ):
        return False
    return True
