import { useEffect, useRef, useState } from "react";
import { Alert, Badge, Button, Card, Group, Stack, Text, Title } from "@mantine/core";
import { IconLock, IconShieldCheck } from "@tabler/icons-react";
import {
  type CustomerSummary, loginMiniApp, logoutMiniApp, readTelegramInitData,
} from "./miniAppClient";

type Props = { language: string };
type Phase = "idle" | "loading" | "ready" | "error";

const labels: Record<string, Record<string, string>> = {
  ru: { title: "Telegram Mini App — тестовый доступ", description: "Вход доступен только в отдельном пилотном окружении. Настоящие VPN-ключи, QR и ссылки здесь не выдаются.", login: "Подтвердить доступ через Telegram", logout: "Выйти", checking: "Проверяем доступ…", denied: "Не удалось подтвердить доступ. Проверьте доступность пилота.", missing: "Откройте эту страницу внутри поддерживаемого Telegram Mini App.", available: "Авторизованный read-only просмотр", plan: "Тариф", status: "Статус", expiry: "Срок действия", locations: "Доступные локации", unknown: "Нет данных", logoutFailed: "Не удалось подтвердить выход. Серверная сессия может оставаться действующей до истечения срока.", exited: "Выход подтверждён.", disabled: "Только пилот" },
  en: { title: "Telegram Mini App — pilot access", description: "Login is available only in an isolated pilot. No real VPN keys, QR codes or subscription links are issued.", login: "Verify access with Telegram", logout: "Sign out", checking: "Verifying access…", denied: "Unable to verify access. Check pilot availability.", missing: "Open this page in a supported Telegram Mini App.", available: "Authorized read-only view", plan: "Plan", status: "Status", expiry: "Expiration", locations: "Available locations", unknown: "No data", logoutFailed: "Logout could not be confirmed. The server session may remain active until expiry.", exited: "Logout confirmed.", disabled: "Pilot only" },
  zh: { title: "Telegram Mini App — 试点访问", description: "仅在隔离的试点环境中允许登录。不会提供真实 VPN 密钥、二维码或订阅链接。", login: "通过 Telegram 验证访问权限", logout: "退出", checking: "正在验证…", denied: "无法验证访问权限。请检查试点是否可用。", missing: "请在受支持的 Telegram Mini App 中打开此页面。", available: "已授权的只读视图", plan: "套餐", status: "状态", expiry: "到期时间", locations: "可用地区", unknown: "无数据", logoutFailed: "无法确认退出。服务器会话可能在到期前仍然有效。", exited: "已确认退出。", disabled: "仅试点" },
  fa: { title: "Telegram Mini App — دسترسی آزمایشی", description: "ورود فقط در محیط آزمایشی جداگانه مجاز است. هیچ کلید، QR یا پیوند اشتراک واقعی صادر نمی‌شود.", login: "تأیید دسترسی با تلگرام", logout: "خروج", checking: "در حال تأیید…", denied: "تأیید دسترسی ممکن نشد. وضعیت دسترسی آزمایشی را بررسی کنید.", missing: "این صفحه را در Telegram Mini App پشتیبانی‌شده باز کنید.", available: "نمای فقط‌خواندنی مجاز", plan: "طرح", status: "وضعیت", expiry: "انقضا", locations: "مکان‌های در دسترس", unknown: "بدون داده", logoutFailed: "خروج تأیید نشد. نشست سرور ممکن است تا انقضا فعال بماند.", exited: "خروج تأیید شد.", disabled: "فقط آزمایشی" },
  fr: { title: "Telegram Mini App — accès pilote", description: "Connexion réservée à un pilote isolé. Aucune clé VPN, aucun QR ni lien d’abonnement réel n’est délivré.", login: "Vérifier avec Telegram", logout: "Déconnexion", checking: "Vérification…", denied: "Impossible de vérifier l’accès. Vérifiez le pilote.", missing: "Ouvrez cette page dans une Mini App Telegram compatible.", available: "Vue autorisée en lecture seule", plan: "Forfait", status: "Statut", expiry: "Expiration", locations: "Régions disponibles", unknown: "Aucune donnée", logoutFailed: "Déconnexion non confirmée. La session serveur peut rester active jusqu’à expiration.", exited: "Déconnexion confirmée.", disabled: "Pilote uniquement" },
};
const statusNames: Record<string, Record<string, string>> = {
  ru: { active: "Активна", disabled: "Выключена", expired: "Истекла", suspended: "Приостановлена", provisioning: "Подключается", unknown: "Нет данных" },
  en: { active: "Active", disabled: "Disabled", expired: "Expired", suspended: "Suspended", provisioning: "Provisioning", unknown: "Unknown" },
  zh: { active: "有效", disabled: "已禁用", expired: "已过期", suspended: "已暂停", provisioning: "开通中", unknown: "未知" },
  fa: { active: "فعال", disabled: "غیرفعال", expired: "منقضی", suspended: "معلق", provisioning: "در حال فعال‌سازی", unknown: "نامشخص" },
  fr: { active: "Actif", disabled: "Désactivé", expired: "Expiré", suspended: "Suspendu", provisioning: "En préparation", unknown: "Inconnu" },
};

/** Mount only via an explicit build-time pilot switch. Never auto-authenticate. */
export function MiniAppPilotPanel({ language }: Props) {
  const t = labels[language] || labels.ru;
  const [phase, setPhase] = useState<Phase>("idle");
  const [summary, setSummary] = useState<CustomerSummary | null>(null);
  const [notice, setNotice] = useState("");
  const busy = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const request = (path: string, options: RequestInit) => window.fetch(path, options);

  async function signIn() {
    if (busy.current) return;
    // Reads only the raw signed initData, at the moment of the deliberate click.
    const raw = readTelegramInitData(window);
    if (!raw) {
      setSummary(null);
      setPhase("error");
      setNotice(t.missing);
      return;
    }
    busy.current = true;
    setPhase("loading");
    setSummary(null);
    setNotice("");
    try {
      const dto = await loginMiniApp(raw, request);
      if (mounted.current) {
        setSummary(dto);
        setPhase("ready");
      }
    } catch {
      if (mounted.current) {
        setSummary(null);
        setPhase("error");
        setNotice(t.denied);
      }
    } finally { busy.current = false; }
  }

  async function signOut() {
    if (busy.current) return;
    busy.current = true;
    setSummary(null); // Clear client-visible subscription data before HTTP.
    setPhase("loading");
    const confirmed = await logoutMiniApp(request);
    if (mounted.current) {
      setPhase(confirmed ? "idle" : "error");
      setNotice(confirmed ? t.exited : t.logoutFailed);
    }
    busy.current = false;
  }

  const status = summary ? (statusNames[language] || statusNames.ru)[summary.status] || t.unknown : t.unknown;
  const expiryText = summary?.expiryTime === null || summary?.expiryTime === undefined
    ? t.unknown
    : new Date(summary.expiryTime).toLocaleDateString(
        ["ru", "en", "zh", "fa", "fr"].includes(language) ? language : "ru", { year: "numeric", month: "short", day: "numeric" });
  return <Card withBorder radius="lg" p="lg" data-testid="d2a-mini-app-pilot">
    <Stack gap="sm">
      <Group justify="space-between">
        <Title order={3}><IconShieldCheck size={20} aria-hidden="true"/> {t.title}</Title>
        <Badge color="gray">{t.disabled}</Badge>
      </Group>
      <Text size="sm">{t.description}</Text>
      {summary && phase === "ready" ? <div role="status" data-testid="d2a-authorized-summary">
        <Text fw={700}><IconLock size={16} aria-hidden="true"/> {t.available}</Text>
        <Text>{t.plan}: {summary.planName || t.unknown}</Text>
        <Text>{t.status}: {status}</Text>
        <Text>{t.expiry}: {expiryText}</Text>
        <Text>{t.locations}: {summary.availableLocations ?? t.unknown}</Text>
      </div> : null}
      {notice && <Alert color={phase === "error" ? "orange" : "blue"} role="status">{notice}</Alert>}
      <Group>
        {summary && phase === "ready"
          ? <Button onClick={() => { void signOut(); }} loading={busy.current || phase === "loading"}>{t.logout}</Button>
          : <Button onClick={() => { void signIn(); }} loading={busy.current || phase === "loading"}>{t.login}</Button>}
      </Group>
    </Stack>
  </Card>;
}
