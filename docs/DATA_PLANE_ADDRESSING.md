# Data-plane адреса и firewall для Inbounds

Этот документ задаёт production-контракт для client-facing адресов Inbound и host firewall.

## Control plane и data plane — разные контуры

Подключение 3x-ui node к Master и подключение VPN-клиента — разные задачи.

- **Control plane**: panel URL / `Node.address`, который используют Master и административные инструменты. Он может оставаться verified HTTPS hostname, например `panel-node.example.com`.
- **Data plane**: адрес, который попадает в клиентские конфиги и subscription для конкретного Inbound. В 3x-ui он определяется через `shareAddrStrategy` / `shareAddr`.

Не меняй `Node.address` только ради того, чтобы в клиентском конфиге появился IP.

Текущая production policy для client-facing Inbounds на direct node:

~~~text
shareAddrStrategy = custom
shareAddr = <public IP ноды>
~~~

Так client dial endpoint не зависит от DNS имени панели.

Не нужно автоматически резолвить panel hostname и сохранять текущий A-record как client endpoint. DNS может быть проксирован, динамически меняться, иметь несколько адресов или намеренно отличаться от VPN data plane. Public data-plane IP должен быть явным операторским значением.

## SNI и Reality names независимы от dial address

При замене client dial address с hostname на IP нельзя переписывать protocol identity fields.

Примеры:

- VLESS Reality: сохраняются настроенные `serverNames` / SNI.
- Hysteria2 TLS: сохраняется настроенный TLS SNI.
- XHTTP/Reality: сохраняются Reality SNI и transport settings.
- AmneziaWG: меняется только host в `Endpoint`; server/client keys и AWG obfuscation profile не меняются.

Поэтому конфиг, который dial'ит IP, но продолжает использовать hostname в TLS/Reality metadata, является нормальным.

## Host firewall входит в readiness Inbound

Наличие listening socket само по себе недостаточно. Каждый внешний порт Inbound должен быть разрешён также в host/provider firewall.

Примеры для UFW:

~~~bash
sudo ufw allow 2053/tcp comment 'vless-reality'
sudo ufw allow 2083/tcp comment 'vless-xhttp'
sudo ufw allow 443/udp comment 'hysteria2'
sudo ufw allow 51820/udp comment 'amneziawg'
~~~

Используй реальные ports/transports конкретного сервера. Эти значения нельзя копировать вслепую в deployment с другой конфигурацией.

Проверка:

~~~bash
sudo ufw status verbose
sudo ss -lntup
~~~

Для AmneziaWG должны одновременно выполняться два условия:

~~~text
UDP listener существует на настроенном порту
firewall явно разрешает этот UDP port
~~~

## Важный нюанс диагностики: tcpdump и netfilter

Наличие входящего пакета в:

~~~bash
sudo tcpdump -ni any udp port <port>
~~~

не доказывает, что пакет дошёл до userspace socket.

Packet capture может увидеть пакет на host interface до того, как последующий INPUT/netfilter rule его отбросит. Если AWG-клиент отправляет пакеты и `tcpdump` видит ingress, но runtime 3x-ui AmneziaWG продолжает показывать:

~~~text
handshake = 0
endpoint = empty
up = 0
down = 0
~~~

сначала проверяй INPUT/UFW/nftables, а уже потом client keys или embedded AWG runtime.

Рекомендуемые read-only проверки:

~~~bash
ss -lunp | grep ":<port>"
sudo ufw status verbose
sudo nft -a list ruleset
sudo iptables -nvL INPUT --line-numbers
~~~

## Production finding: AmneziaWG блокировался host firewall

На production AmneziaWG inbound получал UDP-пакеты на VPS interface, но handshake не завершался. Тот же `handshake=0` воспроизводился на существующем Inbound, direct client config и новом локальном diagnostic Inbound.

Root cause: UFW работал с default-deny INPUT, а allow rule для AWG UDP port отсутствовал. После явного открытия production AWG UDP port заработали и direct client config, и subscription path.

Этот finding позволил исключить несколько ложных направлений диагностики:

- hostname vs IP не был причиной AWG failure;
- subscription conversion не был причиной;
- Master/direct-node synchronization не был причиной;
- сохранённые AWG keys и сгенерированные profiles не были причиной;
- наличие UDP в `tcpdump` не означало delivery до socket.

После исправления firewall client endpoint снова перевели на явный public IP через `shareAddrStrategy=custom`; subscription smoke прошёл.

## Acceptance checklist новой direct node

Перед тем как считать новую node готовой к client traffic:

1. Оставить panel URL / `Node.address` на verified HTTPS для control plane.
2. Зафиксировать явный public data-plane IP ноды.
3. Для каждого client-facing Inbound выставить и прочитать обратно `shareAddrStrategy=custom` и ожидаемый public IP.
4. При смене dial address сохранить protocol-specific SNI/Reality names.
5. Открыть точные TCP/UDP ports в UFW/provider firewall.
6. Проверить listeners через `ss`.
7. Обновить реальную subscription и убедиться, что endpoint использует ожидаемый IP.
8. Выполнить client smoke каждого protocol.
9. Для AmneziaWG после smoke проверить handshake/counters runtime.
10. Удалить временные diagnostic Inbounds и удалить/ротировать временные credentials/keys, использованные в troubleshooting.

## Будущий product hardening

Предпочтительное направление — отдельный явный node-level data-plane address/public IP, которым управляет оператор. При создании/деплое node-hosted Inbounds этот адрес может использоваться как default для share address.

Требования безопасности:

- никакого неявного DNS→IP persistence;
- никаких изменений SNI/Reality values;
- явная validation введённого адреса;
- mutation read-back после применения share-address change;
- никаких secret values в audit/log output;
- существующие nodes без явного data-plane metadata не меняются автоматически.

Tracking: GitHub issue #219.
