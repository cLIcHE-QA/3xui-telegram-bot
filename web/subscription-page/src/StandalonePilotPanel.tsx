import { useEffect, useRef, useState } from "react";
import { Alert, Badge, Button, Card, Code, Group, Stack, Text, Title } from "@mantine/core";
import { IconBrowser, IconLock } from "@tabler/icons-react";
import type { CustomerSummary } from "./miniAppClient";
import {
  startStandalone, completeStandalone,
  cancelStandalone, logoutStandalone,
} from "./standaloneClient";

type Props = { language: string };
type Phase = "idle" | "starting" | "pending" | "working" | "ready" | "error";

const labels: Record<string, Record<string, string>> = {
  ru: {
    title: "Отдельный вход в браузере", pilot: "Только пилот",
    description: "Подтверждение происходит отдельно в приватном чате официального Telegram-бота. Код запроса не является паролем или ссылкой на подписку.",
    start: "Создать запрос", code: "Код подтверждения", confirm: "Проверить подтверждение",
    cancel: "Отменить запрос", logout: "Выйти", waiting: "Ожидается явное подтверждение в приватном Telegram-чате. Подтверждайте только созданные вами запросы.",
    caution: "Проверенный обработчик Telegram-бота ещё не подключён к этому тестовому интерфейсу. Настоящий вход пока недоступен.",
    denied: "Не удалось подтвердить вход. Создайте новый запрос или проверьте пилотный доступ.",
    failedCancel: "Отмена не подтверждена сервером. Запрос автоматически истечёт.",
    failedLogout: "Выход не подтверждён сервером. Сессия может оставаться действующей до истечения срока.",
    cancelled: "Запрос отменён", loggedOut: "Выход подтверждён", ready: "Доступ подтверждён — только просмотр",
    plan: "Тариф", status: "Статус", expiry: "Срок", locations: "Локации", unknown: "Нет данных",
  },
  en: {
    title: "Standalone browser sign-in", pilot: "Pilot only",
    description: "Approval must happen separately in the official Telegram bot's private chat. The challenge code is not a password or subscription link.",
    start: "Create request", code: "Approval code", confirm: "Check approval",
    cancel: "Cancel request", logout: "Sign out", waiting: "Waiting for explicit approval in a private Telegram chat. Only approve requests you initiated.",
    caution: "The verified Telegram bot handler is not connected to this test interface yet. Real sign-in is unavailable.",
    denied: "Sign-in could not be confirmed. Start a new request or check pilot access.",
    failedCancel: "Server did not confirm cancellation. This request will expire.",
    failedLogout: "Server did not confirm sign-out. The session may remain active until expiry.",
    cancelled: "Request cancelled", loggedOut: "Sign-out confirmed", ready: "Authorized read-only access",
    plan: "Plan", status: "Status", expiry: "Expires", locations: "Locations", unknown: "Unknown",
  },
  fr: {
    title: "Connexion navigateur autonome", pilot: "Pilote uniquement",
    description: "L'approbation se fait séparément dans le chat privé du bot Telegram officiel. Le code n'est ni un mot de passe ni un lien d'abonnement.",
    start: "Créer une demande", code: "Code de confirmation", confirm: "Vérifier l'approbation",
    cancel: "Annuler", logout: "Se déconnecter", waiting: "Approbation privée explicite en attente. N'approuvez que votre propre demande.",
    caution: "Le bot Telegram vérifié n'est pas encore connecté à cette interface test. La connexion réelle est indisponible.",
    denied: "Connexion non confirmée. Recréez une demande ou vérifiez le pilote.",
    failedCancel: "Annulation non confirmée. La demande expirera.",
    failedLogout: "Déconnexion non confirmée. La session peut rester active jusqu'à expiration.",
    cancelled: "Demande annulée", loggedOut: "Déconnexion confirmée", ready: "Vue autorisée en lecture seule",
    plan: "Forfait", status: "Statut", expiry: "Expiration", locations: "Régions", unknown: "Inconnu",
  },
  zh: {
    title: "独立浏览器登录", pilot: "仅限试点",
    description: "必须在官方 Telegram 机器人的私人聊天中另行确认。请求码既不是密码，也不是订阅链接。",
    start: "创建请求", code: "确认码", confirm: "检查确认",
    cancel: "取消请求", logout: "退出", waiting: "正在等待 Telegram 私聊中的明确确认。仅确认由您创建的请求。",
    caution: "经验证的 Telegram 机器人尚未连接测试界面，真实登录不可用。",
    denied: "无法确认登录。请重新创建请求或检查试点权限。",
    failedCancel: "服务器未确认取消。请求会自动过期。",
    failedLogout: "服务器未确认退出。会话可能持续至到期。",
    cancelled: "请求已取消", loggedOut: "已确认退出", ready: "已授权的只读视图",
    plan: "套餐", status: "状态", expiry: "到期", locations: "地区", unknown: "未知",
  },
  fa: {
    title: "ورود مستقل از مرورگر", pilot: "فقط آزمایشی",
    description: "تأیید باید جداگانه در گفت‌وگوی خصوصی ربات رسمی تلگرام انجام شود. کد درخواست نه رمز است و نه لینک اشتراک.",
    start: "ایجاد درخواست", code: "کد تأیید", confirm: "بررسی تأیید",
    cancel: "لغو درخواست", logout: "خروج", waiting: "در انتظار تأیید صریح در چت خصوصی تلگرام؛ فقط درخواست خودتان را تأیید کنید.",
    caution: "اتصال ربات تأییدشده به این رابط آزمایشی هنوز انجام نشده است. ورود واقعی در دسترس نیست.",
    denied: "ورود تأیید نشد. درخواست تازه بسازید یا دسترسی آزمایشی را بررسی کنید.",
    failedCancel: "لغو توسط سرور تأیید نشد. درخواست منقضی می‌شود.",
    failedLogout: "خروج تأیید نشد. نشست ممکن است تا انقضا فعال بماند.",
    cancelled: "درخواست لغو شد", loggedOut: "خروج تأیید شد", ready: "نمای فقط‌خواندنی مجاز",
    plan: "طرح", status: "وضعیت", expiry: "انقضا", locations: "مکان‌ها", unknown: "نامشخص",
  },
};

export function StandalonePilotPanel({ language }: Props) {
  const t = labels[language] ?? labels.ru;
  const [phase, setPhase] = useState<Phase>("idle");
  const [challenge, setChallenge] = useState("");
  const [summary, setSummary] = useState<CustomerSummary | null>(null);
  const [notice, setNotice] = useState("");
  const busy = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const transport = (path: string, options: RequestInit) => window.fetch(path, options);

  async function begin() {
    if (busy.current) return;
    busy.current = true;
    setSummary(null);
    setChallenge("");
    setNotice("");
    setPhase("starting");
    try {
      const result = await startStandalone(transport);
      if (mounted.current) {
        setChallenge(result.challenge); // Readable public request ID, NOT identity.
        setPhase("pending");
      }
    } catch {
      if (mounted.current) { setPhase("error"); setNotice(t.denied); }
    } finally { busy.current = false; }
  }

  async function finish() {
    if (!challenge || busy.current) return;
    busy.current = true;
    setPhase("working");
    try {
      const result = await completeStandalone(challenge, transport);
      if (mounted.current) {
        if (result.state === "pending") {
          setPhase("pending");
          setNotice(t.waiting);
        } else {
          setSummary(result.subscription);
          setChallenge("");
          setPhase("ready");
          setNotice("");
        }
      }
    } catch {
      if (mounted.current) { setPhase("pending"); setNotice(t.denied); }
    } finally { busy.current = false; }
  }

  async function cancel() {
    if (!challenge || busy.current) return;
    busy.current = true;
    setPhase("working");
    const confirmed = await cancelStandalone(challenge, transport);
    if (mounted.current) {
      if (confirmed) { setChallenge(""); setPhase("idle"); setNotice(t.cancelled); }
      else { setPhase("pending"); setNotice(t.failedCancel); }
    }
    busy.current = false;
  }

  async function logout() {
    if (busy.current) return;
    busy.current = true;
    setSummary(null);
    setChallenge("");
    setPhase("working");
    const confirmed = await logoutStandalone(transport);
    if (mounted.current) {
      setPhase(confirmed ? "idle" : "error");
      setNotice(confirmed ? t.loggedOut : t.failedLogout);
    }
    busy.current = false;
  }

  const expireDate = summary?.expiryTime == null ? t.unknown
    : new Date(summary.expiryTime).toLocaleDateString(
        ["ru", "en", "fr", "zh", "fa"].includes(language) ? language : "ru");
  return <Card withBorder radius="lg" p="lg" data-testid="d2b-standalone-pilot">
    <Stack gap="sm">
      <Group justify="space-between">
        <Title order={3}><IconBrowser size={20} aria-hidden="true"/> {t.title}</Title>
        <Badge color="gray">{t.pilot}</Badge>
      </Group>
      <Text size="sm">{t.description}</Text>
      <Alert color="yellow" role="status">{t.caution}</Alert>
      {phase === "pending" || (phase === "working" && challenge)
        ? <Stack gap="xs">
          <Text fw={700}>{t.code}:</Text>
          <Code data-testid="d2b-challenge">{challenge}</Code>
          <Text size="sm">{t.waiting}</Text>
          <Group>
            <Button onClick={() => { void finish(); }} disabled={busy.current}>{t.confirm}</Button>
            <Button variant="outline" onClick={() => { void cancel(); }} disabled={busy.current}>{t.cancel}</Button>
          </Group>
        </Stack>
        : null}
      {phase === "ready" && summary ? <Stack gap="xs" role="status" data-testid="d2b-standalone-summary">
        <Text fw={700}><IconLock size={16} aria-hidden="true"/> {t.ready}</Text>
        <Text>{t.plan}: {summary.planName || t.unknown}</Text>
        <Text>{t.status}: {summary.status}</Text>
        <Text>{t.expiry}: {expireDate}</Text>
        <Text>{t.locations}: {summary.availableLocations ?? t.unknown}</Text>
        <Button onClick={() => { void logout(); }} disabled={busy.current}>{t.logout}</Button>
      </Stack> : null}
      {(phase === "idle" || phase === "error" || phase === "starting")
        && <Button loading={phase === "starting"} onClick={() => { void begin(); }} disabled={busy.current}>{t.start}</Button>}
      {notice && <Alert color={phase === "error" ? "orange" : "blue"} role="status">{notice}</Alert>}
    </Stack>
  </Card>;
}
