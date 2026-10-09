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

## 3. Установка официального Linux Client на test VPS

Используй только официальный [Cloudflare packages](https://pkg.cloudflareclient.com/) и [Linux WARP guide](https://developers.cloudflare.com/warp-client/get-started/linux/). Перед импортом GPG проверь официальный источник и fingerprint; не используй curl|sh, сторонний mirror, trusted=yes или отключение APT signature verification. Для уже установленного старого клиента проверь актуальную процедуру ротации signing key.

Следующие команды предназначены для выполнения **по одной**, с проверкой каждого результата:

~~~bash
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg lsb-release
curl -fsSLo cloudflare-warp-pubkey.gpg https://pkg.cloudflareclient.com/pubkey.gpg
gpg --show-keys --with-fingerprint cloudflare-warp-pubkey.gpg
gpg --dearmor -o cloudflare-warp-archive-keyring.gpg cloudflare-warp-pubkey.gpg
sudo install -D -m 0644 cloudflare-warp-archive-keyring.gpg /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
printf 'deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ %s main\n' "$(lsb_release -cs)" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
sudo apt-get update
apt-cache policy cloudflare-warp
sudo apt-get install cloudflare-warp
~~~

Остановись при неподдерживаемом codename, архитектуре, ошибке APT signature или неожиданном fingerprint. До подключения проверь установленный CLI и systemd:

~~~bash
warp-cli --help
warp-cli mode --help
warp-cli status
systemctl is-active warp-svc
~~~

Не считай статус systemd-сервиса доказательством активного туннеля или доступности входящих подключений. Синтаксис CLI может меняться: перед применением команд убедись, что они поддерживаются установленной версией.

**Zero Trust/headless Linux:** управляемый device enrollment через organization/service-token/MDM — отдельный flow согласно [Cloudflare headless Linux](https://developers.cloudflare.com/cloudflare-one/tutorials/deploy-client-headless-linux/). Не заменяй его consumer registration и не помещай service tokens, mdm.xml или enrollment в GitHub, Telegram, логи и общий backup. Создание таких секретов не входит в #357.

## 4. Подключение только на canary

ВНИМАНИЕ: команды ниже изменяют сеть и допускаются **лишь** при работающей независимой консоли, сохранённом baseline и согласованном rollback. Не запускать на Master или production direct nodes по одному факту наличия инструкции.

### 4.1 Consumer DNS-only

~~~bash
warp-cli registration new
warp-cli mode doh
warp-cli connect
warp-cli status
~~~

Каждая команда выполняется отдельно. Проверь resolvectl, разрешение имен panel/API, локальных доменов и исходящий HTTPS. В DNS-only отсутствие warp=on в Cloudflare trace — ожидаемое поведение: IP-трафик не должен туннелироваться. При нарушении resolver сразу переходи к откату.

### 4.2 Consumer full tunnel / Traffic and DNS

Только на изолированной canary и после проверки OOB:

~~~bash
warp-cli mode warp+doh
warp-cli connect
warp-cli status
ip -4 route show default
ip -6 route show default
ip rule show
~~~

Проверь один направленный запрос:

~~~bash
curl -4 --fail --silent --show-error https://www.cloudflare.com/cdn-cgi/trace
~~~

Поле warp=on относится лишь к данному исходящему запросу **с хоста**. Не публикуй полный trace. Оно **не** доказывает работоспособность нового SSH, входящих TCP/UDP VPN, контейнеров, source-IP ACL или 3x-ui. IPv6 проверь отдельно, если он реально использовался до теста. WARP MASQUE/WireGuard transports, порты и MTU нельзя менять вместе с UFW или Xray ради случайной диагностики.

### 4.3 Управляемые Split Tunnels

Для Cloudflare One Zero Trust используй **Team & Resources → Devices → Device profiles → General profiles → Split Tunnels**:

- **Include:** через туннель идут только перечисленные назначения; для узкого egress use-case предпочтительнее после отдельного review.
- **Exclude:** все остальные назначения идут через WARP; неправильно исключённые публичные IP/CIDR могут нарушить обратный SSH, panel API и клиентский трафик.
- DNS policy, private/local domains (Local Domain Fallback), Docker/bridge subnet и IPv4/IPv6 проверяются отдельно. Не вводи универсальные исключения 0.0.0.0/0 или ::/0 вслепую.
- Убедись, что применился именно согласованный device profile, проверь настройки командой warp-cli settings. Изменения policy могут применяться с задержкой. Always-on/locked switch могут блокировать локальный disconnect — согласуй централизованный override до старта.

См. [Split Tunnels](https://developers.cloudflare.com/cloudflare-one/team-and-resources/devices/cloudflare-one-client/configure/route-traffic/split-tunnels/) и [Device settings](https://developers.cloudflare.com/cloudflare-one/team-and-resources/devices/cloudflare-one-client/configure/settings/).

## 5. Раздельный health/readiness и reboot smoke

Любой FAIL — остановка rollout и откат, а не попытка «включить ещё раз».

| Контур | Проверка |
|---|---|
| Console/SSH | OOB всё ещё доступна; **новый внешний SSH login**, а не только сохранившаяся сессия; route обратных пакетов |
| Control plane | verified HTTPS Master→direct 3x-ui и bot→direct admin; не раскрывать API credentials |
| Host Control | локальный 127.0.0.1:18181, TLS management proxy и allowlist source IP Master; стабильная node.id binding |
| Master/Backup | health, SQLite, off-site DNS/egress, scheduled job отдельно; Connected не означает backup PASS |
| Docker | DNS и исходящий IP контейнера, healthz и 3x-ui API; network namespace может использовать иной маршрут |
| VPN data plane | внешний real subscription/reconnect на public IP ноды и точный TCP/UDP port |
| TLS/Reality | неизменные serverNames/SNI, XHTTP settings и успешный handshake |
| Hysteria2/AWG | внешний UDP smoke; для AmneziaWG handshake/counters и проверка INPUT/UFW |
| IPv4/IPv6 | обе реально используемые IP families отдельно |
| Reboot | только на canary, заранее согласованный restart; после — warp-cli status, warp-svc, новый SSH, API и реальный VPN |

**Инвариант проекта:** Node.address/panel URL остаётся verified HTTPS **control-plane hostname**. Адрес в подписке — явный public node IP через shareAddrStrategy=custom, shareAddr=<public IP>. Нельзя записывать WARP egress IP в Inbound shareAddr автоматически, менять Reality SNI или приписывать успех WARP состоянию Xray. Подробнее: [Data-plane addressing](DATA_PLANE_ADDRESSING.md), [Node onboarding](NODE_ONBOARDING.md).

Фиксируй в evidence только scrubbed PASS/FAIL, режим, версию, policy revision, время МСК и релевантную причину отката. Не публикуй реальные IP администраторов, секреты, полный diagnostic zip, subscription URLs, enrollment.

## 6. Откат и аварийное восстановление

Из рабочей независимой консоли, **по одной команде**:

~~~bash
warp-cli disconnect
warp-cli status
ip -4 route show default
ip -6 route show default
ip rule show
~~~

Статус Disconnected не означает автоматического восстановления DNS и routes. Сверь baseline, проверь resolvectl, новый SSH, verified HTTPS к API, Host Control, Docker и внешний VPN client. Если клиент снова подключается автоматически — проверь Zero Trust auto-connect/locked-switch policy и используй санкционированный централизованный override.

Если CLI завис/недоступен, **только через OOB**:

~~~bash
sudo systemctl stop warp-svc
~~~

Затем снова проверь фактический DNS/route и входящий трафик. Для предотвращения повторного подключения после reboot, лишь по отдельному решению:

~~~bash
systemctl is-enabled warp-svc
sudo systemctl disable warp-svc
~~~

Disable не равно stop. Не используй очистку таблиц маршрутизации и firewall (ip route flush, iptables -F, nft flush ruleset, ufw disable), не стирай resolv.conf, не рестартуй Docker/Xray вслепую. Регистрация WARP / Zero Trust service-token не удаляется ради обычного disconnect; удаление пакета также необязательно и допустимо отдельно только после восстановления системы. При потере SSH — использовать OOB/rescue провайдера, а не превращать Host Control в общий shell gateway.

## 7. Типовые проблемы

- warp-cli Connected, но DNS/API не работает: проверить режим, локальный resolver и фактический device profile, не ослаблять TLS verification.
- warp=off при DNS-only либо Include policy вне целевых назначений — нормально; проверка должна соответствовать режиму.
- WARP egress OK, но Xray/SSH недоступны: проверить **обратный route**, UFW/provider firewall, NAT, IPv4/IPv6 и public listener IP. Не менять shareAddr на адрес Cloudflare egress.
- warp-svc active не равен активному туннелю или работоспособному data plane.
- Docker и forwarding Xray могут идти по маршруту, отличному от хостового WARP. Не пытаться исправить это неподтверждённым iptables/policy routing.
- WARP вновь подключается после reboot: проверить автоподключение в управляемой policy, а не повторять blind disconnect.

## 8. Acceptance checklist для canary

- [ ] OOB-консоль, backup, исходные маршруты/DNS/firewall и rollback зафиксированы и проверены.
- [ ] OS, архитектура, ресурсы, подпись официального пакета и CLI подходят.
- [ ] Один режим выбран и проверен; full tunnel не включён по умолчанию на production.
- [ ] DNS, IPv4/IPv6, новый SSH, панель, Host Control, Docker, backup/off-site проверены независимо.
- [ ] Реальный внешний VPN connect/handshake для каждого активного протокола; shareAddr/SNI не переписывались.
- [ ] После согласованного reboot на **test VPS** сохраняются OOB, SSH, API, VPN и ожидаемое состояние WARP.
- [ ] При FAIL — rollback подтверждён фактическими маршрутами и доступом, а не одним статусом CLI.
- [ ] Результат clean от секретов и приватных endpoint; lab PASS не означает production acceptance.
- [ ] Документационный PR не изменяет VPS, Docker, firewall и 3x-ui.

## 9. Источники и статус проверки

Сверено 2026-10-09 с официальными источниками:

1. [Cloudflare Linux WARP installation](https://developers.cloudflare.com/warp-client/get-started/linux/).
2. [Cloudflare official APT repository/GPG](https://pkg.cloudflareclient.com/).
3. [Supported Linux OS/resources](https://developers.cloudflare.com/warp-client/get-started/).
4. [WARP modes](https://developers.cloudflare.com/warp-client/warp-modes/).
5. [Cloudflare One Split Tunnels](https://developers.cloudflare.com/cloudflare-one/team-and-resources/devices/cloudflare-one-client/configure/route-traffic/split-tunnels/).
6. [Headless Linux Zero Trust enrollment](https://developers.cloudflare.com/cloudflare-one/tutorials/deploy-client-headless-linux/).
7. [Device settings / auto-connect](https://developers.cloudflare.com/cloudflare-one/team-and-resources/devices/cloudflare-one-client/configure/settings/).

Операторская исходная ссылка: [AézaWiki WARP, архив 2026-04-08](https://web.archive.org/web/20260408162809/https://wiki.aeza.net/ru/guides/warp/). Архив **не удалось открыть** при сверке. Его материал и команды здесь **не копировались**, приведён оригинальный текст по официальному upstream и внутренним сетевым контрактам проекта.

**Scope #357:** docs-only. Никаких команд по установке/подключению WARP на production/VPS не выполнялось и не планируется в рамках issue.
