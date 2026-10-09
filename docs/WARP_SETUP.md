# Cloudflare WARP для Master VPS и direct nodes

**Назначение:** опциональное руководство оператора по официальному Cloudflare WARP Linux Client на Debian/Ubuntu. Это не часть обязательной установки 3x-ui Telegram Bot и не разрешение на работу с production.

> **STOP:** перед любым подключением WARP необходимы отдельное согласование изменения сети, независимая от SSH консоль VPS-провайдера (KVM/Serial/VNC), сохранённый baseline маршрутизации/DNS/firewall и проверенный план rollback. Даже при успешном подключении WARP можно потерять SSH, публичный 3x-ui API, Host Control, Docker egress или VPN-доступ клиентов. Все изменяющие сеть шаги ниже — **только для отдельной test/canary VPS**.

Host-level WARP не устанавливается Telegram-ботом, Host Control или Deploy Agent. Он не меняет автоматически Xray outbound, client-facing Inbound address, SNI/Reality и не гарантирует туннелирование VPN-трафика клиентов через Cloudflare.

## 1. Режимы и границы

| Режим | Что меняет | Для чего |
|---|---|---|
| **DNS-only / DoH** | DNS хоста, не туннелирует обычный IP-трафик | Лабораторная проверка DNS и resolver |
| **Traffic and DNS / full tunnel** | Хостовый egress и DNS, возможна смена routes/source IP | Лишь canary с OOB-консолью и внешним smoke |
| **Include Split Tunnels** (Cloudflare One / Zero Trust) | Через WARP проходят только выбранные destination CIDR/домены | Узкий управляемый egress при наличии device profile |
| **Exclude Split Tunnels** (Cloudflare One / Zero Trust) | Через WARP идёт всё, кроме исключений | Рискованно для публичных серверов и обратного SSH/VPN маршрута |
| **wgcf / third-party WireGuard scripts / Xray outbound** | Совершенно другой стек | Вне scope #357: не подменять ими официальный Linux Client |

**Различай consumer WARP и управляемый Cloudflare One.** Split Tunnels — device-profile policy Zero Trust, не consumer-переключатель CLI. IP routing и DNS policy — разные области: даже исключённые сети могут получать DNS через Gateway, а для внутреннего домена нужен Local Domain Fallback. WARP не обеспечивает анонимность и не гарантирует страну выхода.

Для Master и direct nodes **не выбирай full tunnel по умолчанию**. Этот документ не даёт команды для установки в Xray WARP outbound или автоматического изменения host routing.

## 2. Требования и условия остановки

На дату сверки официальных источников (**2026-10-09**) поддерживаются Ubuntu 22.04/24.04/26.04 LTS и Debian 12/13, x86-64/ARM64. Для Linux без desktop Cloudflare заявляет минимум **3 vCPU, 1 GiB RAM, 250 MiB disk**, рекомендует 4 vCPU, 2 GiB RAM и 500 MiB disk. Не считай любую небольшую VPS, подходящую для 3x-ui, автоматически поддерживаемой WARP; проверь архитектуру и пакет для конкретного выпуска ОС.

Перед изменением нужно:

1. Проверить **out-of-band console** провайдера на практике. Вторая SSH-сессия **не** заменяет независимую консоль.
2. Создать независимый snapshot/backup и записать IPv4/IPv6 default route, policy rules, интерфейсы, DNS resolver, UFW/nftables и provider firewall. Сохранить исходный публичный IP узла и обратный путь ответов на SSH/HTTPS/VPN.
3. Подготовить внешние проверки: новый SSH login; verified HTTPS Master→direct node и bot→3x-ui admin API; Host Control proxy и source-IP allowlist; Docker DNS/egress, off-site backup; Reality, XHTTP, Hysteria2 и AmneziaWG подключения настоящих клиентов.
4. Определить ответственного, окно работы, исход rollback и STOP condition. Не менять одновременно WARP, firewall, Docker, Xray и адреса подписок.
5. На production прежде закрывать отдельные Full Backup/DR и v5 acceptance gates; docs-only задача #357 не разрешает экспериментировать с сетью до них.

**STOP**, если OOB нет, ОС/ресурсы не подходят, отсутствует независимый backup либо невозможно проверить внешний data plane.

### Read-only baseline на отдельной test VPS

Каждую команду выполняй **отдельно** и проверяй вывод до следующего шага:

~~~bash
cat /etc/os-release
uname -m
nproc
free -h
ip -4 route show default
ip -6 route show default
ip rule show
ip -br addr
resolvectl status
sudo ss -lntup
sudo ufw status verbose
systemctl is-active x-ui.service
~~~

resolvectl может отсутствовать без systemd-resolved, UFW может не применяться. Отсутствие IPv6 default route не означает, что его надо создавать. На Master дополнительно зафиксируй read-only Docker networks и доступность контейнера. Не публикуй network baseline, IP оператора, credential и приватные endpoints.

Для источника SSH и каждого административного endpoint дополнительно проверь **конкретный обратный маршрут** через команду вида:

~~~text
ip -4 route get <адрес-внешнего-SSH-клиента>
~~~

Это placeholder; никогда не выполняй строку с угловыми скобками без подстановки. Если заранее неясно, какой uplink использует ответ на входящий пакет, подключать WARP нельзя.
