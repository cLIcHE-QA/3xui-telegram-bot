# Data-plane addressing and inbound firewall

This document defines the production contract for client-facing inbound addresses and host firewall rules.

## Control plane vs data plane

3x-ui node connectivity and client VPN connectivity are separate concerns.

- **Control plane**: the node panel URL / `Node.address` used by Master and administrative tooling. It may remain a verified HTTPS hostname such as `panel-node.example.com`.
- **Data plane**: the address written into client configs and subscriptions for an inbound. In 3x-ui this is controlled by `shareAddrStrategy` / `shareAddr`.

Do not change `Node.address` merely to make client configs use an IP address.

For the current production deployment policy, node-hosted client inbounds should use:

~~~text
shareAddrStrategy = custom
shareAddr = <node public IP>
~~~

This keeps the client dial endpoint independent from panel DNS.

Do **not** silently resolve a panel hostname and persist its current A record as the client endpoint. DNS may be proxied, dynamic, multi-address, or intentionally separate from the VPN data plane. The public data-plane IP must be an explicit operator-owned value.

## SNI and Reality names are separate

Changing the client dial address from a hostname to an IP must not rewrite protocol identity fields.

Examples:

- VLESS Reality: keep the configured Reality `serverNames` / SNI.
- Hysteria2 TLS: keep the configured TLS SNI.
- XHTTP/Reality: keep Reality SNI and transport fields unchanged.
- AmneziaWG: only the `Endpoint` host changes; the AWG server/client keys and obfuscation profile do not.

A typical resulting client config may therefore dial an IP while still using a hostname in TLS/Reality metadata. That is expected.

## Host firewall is part of inbound readiness

A listening socket alone is not sufficient. Every exposed inbound port must also be permitted by the host/provider firewall.

For UFW, examples:

~~~bash
sudo ufw allow 2053/tcp comment 'vless-reality'
sudo ufw allow 2083/tcp comment 'vless-xhttp'
sudo ufw allow 443/udp comment 'hysteria2'
sudo ufw allow 51820/udp comment 'amneziawg'
~~~

Use the actual ports and transports configured on the server. Do not copy these examples blindly when the deployment differs.

Verification:

~~~bash
sudo ufw status verbose
sudo ss -lntup
~~~

For AmneziaWG, verify both:

~~~text
UDP listener exists on the configured port
firewall explicitly allows that UDP port
~~~

## Diagnostic caveat: tcpdump vs netfilter

Seeing an inbound packet in:

~~~bash
sudo tcpdump -ni any udp port <port>
~~~

does **not** prove that the packet reached the userspace socket.

Packet capture can observe traffic on the host interface before a later INPUT/netfilter rule drops it. If an AWG client sends packets, `tcpdump` sees ingress, but the 3x-ui AmneziaWG runtime still reports:

~~~text
handshake = 0
endpoint = empty
up = 0
down = 0
~~~

check INPUT/UFW/nftables before investigating client keys or the embedded AWG runtime.

Recommended read-only checks:

~~~bash
ss -lunp | grep ":<port>"
sudo ufw status verbose
sudo nft -a list ruleset
sudo iptables -nvL INPUT --line-numbers
~~~

## Production incident note: Finland AmneziaWG

A Finland AmneziaWG inbound received UDP packets at the VPS interface but never completed a handshake. The existing inbound, a direct client config, and a newly generated local diagnostic inbound all reproduced the same `handshake=0` state.

The root cause was UFW default-deny INPUT without an allow rule for the AWG UDP port. After the production AWG UDP port was explicitly allowed, both the direct client config and subscription path connected successfully.

This incident ruled out several misleading hypotheses:

- panel hostname vs IP was not the AWG failure cause;
- subscription conversion was not the cause;
- Master/sub-node synchronization was not the cause;
- stored AWG key material and generated profiles were not the cause;
- seeing UDP in `tcpdump` was not proof of socket delivery.

After firewall remediation, the Finland client endpoint was switched back to the explicit node public IP through `shareAddrStrategy=custom`, and the subscription smoke passed.

## New direct-node acceptance checklist

Before considering a new node ready for client traffic:

1. Keep the panel URL / `Node.address` on verified HTTPS for the control plane.
2. Record an explicit public data-plane IP for the node.
3. For each client-facing inbound, set and read back `shareAddrStrategy=custom` and the intended public IP.
4. Preserve protocol-specific SNI/Reality names while changing only the dial address.
5. Open the exact TCP/UDP ports in UFW/provider firewall.
6. Verify listeners with `ss`.
7. Refresh a real subscription and confirm the generated endpoint uses the intended IP.
8. Run one client smoke per protocol.
9. For AmneziaWG, confirm runtime handshake/counters after the smoke.
10. Remove temporary diagnostic inbounds and rotate/delete any temporary credentials or keys used during troubleshooting.

## Future product hardening

Preferred implementation direction is an explicit node-level data-plane address/public-IP field owned by the operator. Creation/deployment of node-hosted inbounds can then default their share address to that value.

Safety requirements:

- no implicit DNS-to-IP persistence;
- no rewriting of SNI/Reality values;
- explicit validation of the supplied address;
- mutation read-back after applying share-address changes;
- no secret values in audit/log output;
- existing nodes without explicit data-plane metadata remain unchanged until configured.

Tracked in GitHub issue #219.
