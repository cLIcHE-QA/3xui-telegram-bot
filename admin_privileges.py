from __future__ import annotations

from dataclasses import dataclass
import re


ROLE_LABELS = {
    "owner": "Owner",
    "admin": "Administrator",
    "support": "Support",
    "read_only": "Read-only",
}

ROLE_RANK = {
    "read_only": 10,
    "support": 20,
    "admin": 30,
    "owner": 40,
}


@dataclass(frozen=True)
class Privilege:
    permission_id: str
    label: str
    minimum_role: str


@dataclass(frozen=True)
class CallbackRule:
    permission_id: str
    kind: str
    value: str

    def matches(self, data: str) -> bool:
        if self.kind == "exact":
            return data == self.value
        if self.kind == "prefix":
            return data.startswith(self.value)
        if self.kind == "regex":
            return re.fullmatch(self.value, data) is not None
        raise ValueError(f"Unsupported callback rule kind: {self.kind}")


PRIVILEGES: tuple[Privilege, ...] = (
    Privilege("dashboard.view", "Обзор и разделы /admin", "read_only"),
    Privilege("users.view", "Пользователи и подписки: просмотр", "read_only"),
    Privilege("users.support", "Пользователи: обычные операции жизненного цикла", "support"),
    Privilege("users.admin", "Пользователи: расширенные и разрушительные операции", "admin"),
    Privilege("user_groups.view", "Группы пользователей: просмотр", "read_only"),
    Privilege("user_groups.manage", "Группы пользователей: состав участников", "support"),
    Privilege("user_groups.admin", "Группы пользователей: создание, изменение и удаление", "admin"),
    Privilege("backups.view", "Резервные копии: просмотр", "read_only"),
    Privilege("backups.manage", "Резервные копии: создание и запуск заданий", "admin"),
    Privilege("nodes.view", "Ноды/Master: просмотр", "read_only"),
    Privilege("nodes.manage", "Ноды: добавление и изменение", "admin"),
    Privilege("inbounds.view", "Inbounds: просмотр", "read_only"),
    Privilege("inbounds.manage", "Inbounds/шаблоны: изменения", "admin"),
    Privilege("plans.view", "Тарифы: просмотр", "read_only"),
    Privilege("plans.manage", "Тарифы: изменения", "admin"),
    Privilege("server_groups.view", "Группы серверов: просмотр", "read_only"),
    Privilege("server_groups.manage", "Группы серверов: изменения", "admin"),
    Privilege("hosts.view", "Хосты: просмотр", "read_only"),
    Privilege("hosts.manage", "Хосты: изменения и обнаружение", "admin"),
    Privilege("payments.view", "Платежи: просмотр", "read_only"),
    Privilege("payments.manage", "Платежи: изменения", "admin"),
    Privilege("promo.view", "Промокоды: просмотр", "read_only"),
    Privilege("promo.manage", "Промокоды: изменения", "admin"),
    Privilege("administrators.manage", "Администраторы: управление", "owner"),
    Privilege("administrators.privileges.view", "Роли и права: просмотр", "owner"),
    Privilege("settings.view", "Настройки: просмотр", "read_only"),
    Privilege("settings.manage", "Настройки: изменения", "admin"),
    Privilege("monitoring.view", "Мониторинг/Журналы/Аудит/Задания: просмотр", "read_only"),
    Privilege("website_monitoring.view", "Мониторинг сайтов: просмотр", "read_only"),
    Privilege("website_monitoring.manage", "Мониторинг сайтов: подписки и ручные проверки", "support"),
    Privilege("website_monitoring.admin", "Мониторинг сайтов: глобальные изменения", "admin"),
    Privilege("jobs.manage", "Задания: ручной запуск", "admin"),
    Privilege("alerts.view", "Оповещения: просмотр и ручная проверка", "read_only"),
    Privilege("alerts.manage", "Оповещения: изменение правил", "admin"),
    Privilege("restore.manage", "Аварийное восстановление", "owner"),
    Privilege("host_control.view", "Host Control: просмотр", "read_only"),
    Privilege("host_control.manage", "Host Control: обычные изменения", "admin"),
    Privilege("host_control.destructive", "Host Control: разрушительная остановка", "owner"),
    Privilege("fleet.view", "Операции с нодами: просмотр", "read_only"),
    Privilege("fleet.manage", "Операции с нодами: обслуживание и обновление", "admin"),
    Privilege("versions.view", "Версии и обновления: просмотр", "read_only"),
    Privilege("versions.manage", "Версии и обновления: установка", "admin"),
    Privilege("versions.unlock", "Версии и обновления: снятие блокировки после ручной проверки", "owner"),
    Privilege("bot_updates.manage", "Обновления бота: развёртывание опубликованного релиза", "owner"),
    Privilege("legacy.manage", "Совместимые административные маршруты", "admin"),
)

_PRIVILEGE_BY_ID = {item.permission_id: item for item in PRIVILEGES}


def _rules(permission_id: str, kind: str, *values: str) -> list[CallbackRule]:
    return [CallbackRule(permission_id, kind, value) for value in values]


CALLBACK_RULES: tuple[CallbackRule, ...] = tuple(
    _rules(
        "dashboard.view",
        "exact",
        "admin:home", "admin:dashboard", "admin:stats",
        "admin:section:infrastructure", "admin:section:monitoring", "admin:section:system",
        "admin:health",
    )
    + _rules("legacy.manage", "prefix", "admin:coming:")
    + _rules(
        "users.view",
        "exact",
        "admin:users", "admin:subscriptions", "admin:users:search", "admin:users:noop",
    )
    + _rules("users.view", "regex", r"^admin:users:page:\d+$")
    + _rules("users.view", "prefix", "adminuser:", "adminsub:", "adminsublist:")
    + _rules(
        "users.support",
        "prefix",
        "adminsync:", "adminextend:", "admindisable:", "adminenable:",
        "admin:u:expiry:", "admin:u:traffic:", "admin:u:ip:", "admin:u:note:", "admin:u:name:",
        "admin:u:plan:", "admin:u:planset:", "admin:u:planapplyask:", "admin:u:planapplyrun:",
        "admin:u:group:", "admin:u:groupset:", "admin:u:planprovask:", "admin:u:planprovrun:",
        "admin:u:ibtoggle:", "admin:u:resetask:", "admin:u:resetrun:",
        "admin:u:devdelask:", "admin:u:devdel:",
        "admin:bulk:toggle:", "admin:bulk:run:",
    )
    + _rules(
        "users.support",
        "exact",
        "admin:provision:all:ask", "admin:provision:all:run", "admin:users:bulk",
        "admin:users:create", "admin:users:create:email-default", "admin:users:create:email-custom",
        "admin:users:create:display-skip", "admin:users:create:plan-compat", "admin:users:create:run",
        "admin:bulk:all", "admin:bulk:clear", "admin:bulk:actions",
        "admin:bulk:back", "admin:bulk:close", "admin:bulk:prev", "admin:bulk:next",
    )
    + _rules("users.view", "exact", "admin:bulk:noop")
    + _rules("payments.view", "regex", r"^admin:u:payments:\d+(?::\d+)?$", r"^admin:u:payment:\d+:\d+$")
    + _rules("monitoring.view", "regex", r"^admin:u:activity:\d+(?::\d+)?$")
    + _rules(
        "users.support",
        "regex",
        r"^admin:users:create:plan:\d+$",
        r"^admin:users:create:recover:\d+$",
    )
    + _rules("users.view", "regex", r"^admin:u:\d+$")
    + _rules("users.view", "regex", r"^admin:u:device:\d+:\d+$")
    + _rules("users.support", "regex", r"^admin:u:devdelask:\d+:\d+$", r"^admin:u:devdel:\d+:\d+$")
    + _rules(
        "users.view",
        "prefix",
        "admin:u:prov:", "admin:u:inbounds:", "admin:u:planview:", "admin:u:expiryview:",
        "admin:u:trafficview:", "admin:u:access:", "admin:u:accesscfg:", "admin:u:subview:",
        "admin:u:profile:", "admin:u:more:", "admin:u:connections:", "admin:u:devices:",
        "admin:u:device:", "admin:u:ips:",
    )
    + _rules(
        "users.admin",
        "prefix",
        "admindel:", "admindelask:", "admin:u:provstrictask:",
        "admin:u:subrotateask:", "admin:u:subrotaterun:",
    )
    + _rules("users.support", "regex", r"^admin:u:provrun:\d+:safe$")
    + _rules("users.admin", "exact", "admin:syncall:ask", "admin:syncall:run")
    + _rules("users.admin", "regex", r"^admin:u:provrun:\d+:strict$")
    + _rules(
        "user_groups.view",
        "exact",
        "admin:usergroups", "admin:usergroupadd:cancel",
    )
    + _rules(
        "user_groups.view",
        "regex",
        r"^admin:usergroups:page:\d+$",
        r"^admin:usergroup:\d+$",
        r"^admin:usergroup:members:\d+:\d+$",
        r"^admin:usergroup:member:\d+:\d+$",
        r"^admin:u:audgroups:\d+$",
    )
    + _rules("user_groups.view", "prefix", "admin:usergroup:addcancel:")
    + _rules("user_groups.manage", "prefix", "admin:usergroup:add:")
    + _rules(
        "user_groups.manage",
        "regex",
        r"^admin:usergroup:addpick:\d+:\d+$",
        r"^admin:usergroup:removeask:\d+:\d+$",
        r"^admin:usergroup:remove:\d+:\d+$",
        r"^admin:u:audgroupedit:\d+:\d+$",
        r"^admin:u:audgrouptoggle:\d+:\d+:\d+$",
    )
    + _rules("user_groups.admin", "exact", "admin:usergroupadd:start")
    + _rules(
        "user_groups.admin",
        "prefix",
        "admin:usergroup:rename:", "admin:usergroup:description:",
        "admin:usergroup:deleteask:", "admin:usergroup:delete:",
    )
    + _rules("backups.view", "exact", "admin:backups")
    + _rules(
        "backups.manage",
        "exact",
        "admin:backup:create", "admin:backup:botdb", "admin:backup:full",
    )
    + _rules(
        "nodes.view",
        "exact",
        "admin:nodes", "admin:nodes:noop", "admin:nodes:refresh", "admin:master",
    )
    + _rules("nodes.view", "regex", r"^admin:node:\d+$", r"^admin:node:\d+:readiness$")
    + _rules(
        "nodes.manage",
        "exact",
        "admin:nodeadd:start", "admin:nodeadd:test", "admin:nodeadd:save", "admin:nodeadd:cancel",
    )
    + _rules("nodes.manage", "prefix", "admin:nodeadd:tls:")
    + _rules(
        "nodes.manage",
        "regex",
        r"^admin:nodectl:\d+:(inbounds|maintenance|rename|cancel|backup|restartxray|restartxray:run|updatepanel|updatepanel:run|deleteask|delete:run)$",
    )
    + _rules("inbounds.view", "exact", "admin:infra:inbounds")
    + _rules("inbounds.view", "regex", r"^admin:inbound:\d+$")
    + _rules("inbounds.view", "prefix", "admin:inbound:clients:")
    + _rules(
        "inbounds.manage",
        "prefix",
        "admin:inbound:edit:", "admin:inbound:editfield:", "admin:inbound:editfp:",
        "admin:inbound:setfp:", "admin:inbound:editmode:", "admin:inbound:setmode:",
        "admin:inbound:toggle:", "admin:inbound:syncask:", "admin:inbound:syncrun:",
        "admin:inbound:resetask:", "admin:inbound:resetrun:", "admin:inbound:clone:",
        "admin:inbound:clonetarget:", "admin:inbound:template:",
        "admin:inboundtemplate:deploy:", "admin:inboundtemplate:target:",
        "admin:inboundtemplate:deleteask:", "admin:inbound:deleteask:",
    )
    + _rules("inbounds.manage", "exact", "admin:inboundtemplates")
    + _rules("inbounds.manage", "regex", r"^admin:inboundtemplate:\d+$", r"^admin:inboundtemplate:delete:\d+$", r"^admin:inbound:delete:\d+$")
    + _rules("plans.view", "exact", "admin:plans")
    + _rules("plans.view", "regex", r"^admin:plan:\d+$")
    + _rules("plans.view", "prefix", "admin:plan:groups:", "admin:plan:preview:")
    + _rules(
        "plans.manage",
        "exact",
        "admin:planadd:start", "admin:planadd:save", "admin:planadd:cancel",
    )
    + _rules("plans.manage", "prefix", "admin:planadd:group:", "admin:plan:toggle:", "admin:plan:setgroup:", "admin:plan:default:", "admin:plan:deleteask:", "admin:plan:delete:")
    + _rules("server_groups.view", "exact", "admin:servergroups")
    + _rules("server_groups.view", "regex", r"^admin:servergroup:\d+$")
    + _rules("server_groups.view", "prefix", "admin:servergroup:inbounds:")
    + _rules(
        "server_groups.manage",
        "exact",
        "admin:servergroupadd:start", "admin:servergroupadd:cancel",
    )
    + _rules("server_groups.manage", "prefix", "admin:servergroup:toggle:", "admin:servergroup:inboundmode:", "admin:servergroup:ibtoggle:", "admin:servergroup:deleteask:", "admin:servergroup:delete:")
    + _rules("hosts.view", "exact", "admin:hosts")
    + _rules("hosts.view", "regex", r"^admin:host:\d+$")
    + _rules("hosts.manage", "exact", "admin:hosts:discover", "admin:hostadd:start", "admin:hostadd:cancel")
    + _rules("hosts.manage", "prefix", "admin:hostadd:role:", "admin:host:toggle:", "admin:host:deleteask:", "admin:host:delete:")
    + _rules("payments.view", "exact", "admin:payments")
    + _rules("payments.view", "regex", r"^admin:payment:\d+$")
    + _rules("payments.manage", "exact", "admin:paymentadd:start", "admin:paymentadd:save", "admin:paymentadd:cancel")
    + _rules("payments.manage", "prefix", "admin:payment:status:", "admin:paymentadd:plan:", "admin:paymentadd:status:")
    + _rules("promo.view", "exact", "admin:promo")
    + _rules("promo.view", "regex", r"^admin:promo:\d+$")
    + _rules("promo.manage", "exact", "admin:promoadd:start", "admin:promoadd:save", "admin:promoadd:cancel")
    + _rules("promo.manage", "prefix", "admin:promoadd:type:", "admin:promoadd:plan:", "admin:promo:toggle:", "admin:promo:deleteask:", "admin:promo:delete:")
    + _rules("administrators.manage", "exact", "admin:administrators", "admin:administratoradd:start", "admin:administratoradd:cancel")
    + _rules("administrators.manage", "prefix", "admin:administrator:", "admin:administratoradd:role:")
    + _rules("administrators.privileges.view", "exact", "admin:privileges")
    + _rules("settings.view", "exact", "admin:settings")
    + _rules("settings.manage", "exact", "admin:settings:cancel")
    + _rules("settings.manage", "prefix", "admin:settings:edit:", "admin:settings:reset:")
    + _rules(
        "monitoring.view",
        "exact",
        "admin:traffic", "admin:online", "admin:jobs", "admin:audit", "admin:logs", "admin:logs:nodes",
        "admin:cheburcheck", "admin:cheburcheck:start", "admin:cheburcheck:cancel",
        "admin:cheburcheck:master", "admin:cheburcheck:target:master",
    )
    + _rules(
        "website_monitoring.view",
        "exact",
        "admin:webmon", "admin:webmon:list",
    )
    + _rules(
        "website_monitoring.view",
        "regex",
        r"^admin:webmon:site:\d+$",
        r"^admin:webmon:incidents:\d+$",
    )
    + _rules(
        "website_monitoring.view",
        "exact",
        "admin:webdiag", "admin:webdiag:cancel",
    )
    + _rules(
        "website_monitoring.view",
        "regex",
        r"^admin:webdiag:(whois|dns|http|redirects|cms|seo|pagespeed|sitemap|urllist|qr)$",
        r"^admin:webdiag:site:\d+$",
        r"^admin:webdiag:site:\d+:(whois|dns|http|redirects|cms|seo|pagespeed|sitemap|qr)$",
    )
    + _rules(
        "website_monitoring.manage",
        "exact",
        "admin:webmon:add", "admin:webmon:add:cancel",
    )
    + _rules(
        "website_monitoring.manage",
        "regex",
        r"^admin:webmon:check:\d+$",
        r"^admin:webmon:pause:\d+$",
        r"^admin:webmon:alerts:\d+$",
        r"^admin:webmon:deleteask:\d+$",
        r"^admin:webmon:delete:\d+$",
    )
    + _rules(
        "website_monitoring.admin",
        "exact",
        "admin:webmon:all",
    )
    + _rules(
        "website_monitoring.admin",
        "regex",
        r"^admin:webmon:global:\d+$",
        r"^admin:webmon:globaldeleteask:\d+$",
        r"^admin:webmon:globaldelete:\d+$",
    )
    + _rules("monitoring.view", "regex", r"^admin:audit:\d+$", r"^admin:audit:item:\d+:\d+$", r"^admin:logs:node:\d+$", r"^admin:logs:view:[a-z]+:(50|200):(all|warning|error)$", r"^admin:logs:nview:\d+:(panel|xray|awg):(50|200):(all|warning|error)$")
    + _rules(
        "monitoring.view",
        "regex",
        r"^admin:cheburcheck:(node|host):\d+$",
        r"^admin:cheburcheck:target:(node|host):\d+$",
        r"^admin:cheburcheck:(start|cancel):(monitoring|master|node-\d+)$",
    )
    + _rules("jobs.manage", "exact", "admin:jobs:backup")
    + _rules("alerts.view", "exact", "admin:alerts", "admin:alerts:check")
    + _rules("alerts.manage", "regex", r"^admin:alerts:toggle:[a-z_]+$", r"^admin:alerts:disk:(80|85|90|95)$", r"^admin:alerts:backup:(24|36|48|72)$")
    + _rules("restore.manage", "exact", "admin:restore")
    + _rules("restore.manage", "prefix", "admin:restore")
    + _rules("host_control.view", "regex", r"^admin:hostctl:(m|n[1-9][0-9]{0,18})$")
    + _rules("host_control.destructive", "regex", r"^admin:hostctl:(m|n[1-9][0-9]{0,18}):(sp:(ask|run)|stopcancel|xs:(ask|run))$")
    + _rules("host_control.manage", "regex", r"^admin:hostctl:(m|n[1-9][0-9]{0,18}):(ss|sr|pr|xr):(ask|run)$")
    + _rules("fleet.view", "exact", "admin:fleet", "admin:fleet:health", "admin:fleet:jobs")
    + _rules("fleet.manage", "exact", "admin:fleet:rollout")
    + _rules("fleet.manage", "regex", r"^admin:fleet:mt:(e|x)(:n[1-9][0-9]{0,18}|:review|:run)?$", r"^admin:fleet:ro:(p|x)(:n[1-9][0-9]{0,18}|:review)?$", r"^admin:fleet:ro:x:v:[A-Za-z0-9.-]+$", r"^admin:fleet:run:[0-9a-f]{12}:(canary|continue|cancel)$")
    + _rules("versions.view", "exact", "admin:versions")
    + _rules("versions.view", "regex", r"^admin:ver:(target|panel):(m|n[1-9][0-9]{0,18})$", r"^admin:ver:xray:(m|n[1-9][0-9]{0,18}):[0-9]+$", r"^admin:ver:check:[0-9a-f]{16}$")
    + _rules("versions.view", "regex", r"^admin:ver:op:[0-9a-f]{16}$")
    + _rules("versions.manage", "regex", r"^admin:ver:prepare:(m|n[1-9][0-9]{0,18}):panel$", r"^admin:ver:pick:(m|n[1-9][0-9]{0,18}):[A-Za-z0-9.-]+$", r"^admin:ver:(run|cancel):[0-9a-f]{16}$")
    + _rules("versions.unlock", "regex", r"^admin:ver:unlock:[0-9a-f]{16}$")
    + _rules("bot_updates.manage", "exact", "admin:botupd", "admin:botupd:history", "admin:botupd:choose")
    + _rules(
        "bot_updates.manage",
        "regex",
        r"^admin:botupd:(pre|run|down):v[0-9]+\.[0-9]+\.[0-9]+$",
        r"^admin:botupd:op:[0-9a-f]{32}$",
    )
    # Explicit route declarations below intentionally mirror router filters.
    # They make CI fail when a new admin route appears without a catalog entry,
    # even when an older broader runtime rule would otherwise happen to match it.
    + _rules(
        "legacy.manage",
        "exact",
        "admin:coming:plans", "admin:coming:hosts", "admin:coming:servergroups",
        "admin:coming:traffic", "admin:coming:online", "admin:coming:jobs",
        "admin:coming:audit", "admin:coming:payments", "admin:coming:promo",
        "admin:coming:administrators", "admin:coming:settings", "admin:coming:logs",
    )
    + _rules(
        "nodes.manage",
        "regex",
        r"^admin:nodectl:\d+:inbounds$",
        r"^admin:nodectl:\d+:maintenance$",
        r"^admin:nodectl:\d+:rename$",
        r"^admin:nodectl:\d+:cancel$",
        r"^admin:nodectl:\d+:backup$",
        r"^admin:nodectl:\d+:restartxray$",
        r"^admin:nodectl:\d+:restartxray:run$",
        r"^admin:nodectl:\d+:updatepanel$",
        r"^admin:nodectl:\d+:updatepanel:run$",
        r"^admin:nodectl:\d+:deleteask$",
        r"^admin:nodectl:\d+:delete:run$",
    )
    + _rules(
        "administrators.manage",
        "prefix",
        "admin:administrator:role:", "admin:administrator:toggle:",
        "admin:administrator:deleteask:", "admin:administrator:delete:",
    )
    + _rules("administrators.manage", "regex", r"^admin:administrator:\d+$")
    + _rules("restore.manage", "exact", "admin:restore:history")
    + _rules(
        "restore.manage",
        "regex",
        r"^admin:restore:b:[A-Za-z0-9._-]+$",
        r"^admin:restore:pre:[A-Za-z0-9._-]+$",
        r"^admin:restore:bot:[A-Za-z0-9._-]+$",
        r"^admin:restore:xui:[A-Za-z0-9._-]+$",
        r"^admin:restore:node:[A-Za-z0-9._-]+:\d+$",
        r"^admin:restore:cancel:[A-Za-z0-9._-]+$",
        r"^admin:restore:env:[A-Za-z0-9._-]+$",
        r"^admin:restore:nginx:[A-Za-z0-9._-]+$",
    )
    + _rules(
        "fleet.manage",
        "regex",
        r"^admin:fleet:mt:(e|x)$",
        r"^admin:fleet:mt:(e|x):n[1-9][0-9]{0,18}$",
        r"^admin:fleet:mt:(e|x):review$",
        r"^admin:fleet:mt:(e|x):run$",
        r"^admin:fleet:ro:(p|x)$",
        r"^admin:fleet:ro:(p|x):n[1-9][0-9]{0,18}$",
        r"^admin:fleet:ro:(p|x):review$",
    )
    + _rules("versions.manage", "regex", r"^admin:ver:(run|cancel|check):[0-9a-f]{16}$")
    + _rules(
        "bot_updates.manage",
        "regex",
        r"^admin:botupd:pre:v[0-9]+\.[0-9]+\.[0-9]+$",
        r"^admin:botupd:run:v[0-9]+\.[0-9]+\.[0-9]+$",
        r"^admin:botupd:down:v[0-9]+\.[0-9]+\.[0-9]+$",
    )
    # Exact router-filter declaration for CI route-catalog parity. Runtime role
    # resolution is intentionally handled by the earlier safe/support and
    # strict/admin rules, so this trailing declaration cannot weaken access.
    + _rules("users.admin", "regex", r"^admin:u:provrun:\d+:(safe|strict)$")
)


def privilege_for_callback(data: str) -> Privilege | None:
    value = data or ""
    for rule in CALLBACK_RULES:
        if rule.matches(value):
            return _PRIVILEGE_BY_ID[rule.permission_id]
    return None


def required_role_for_callback(data: str) -> str | None:
    privilege = privilege_for_callback(data)
    return privilege.minimum_role if privilege else None


def declared_route_specs() -> set[tuple[str, str]]:
    return {(rule.kind, rule.value) for rule in CALLBACK_RULES}
