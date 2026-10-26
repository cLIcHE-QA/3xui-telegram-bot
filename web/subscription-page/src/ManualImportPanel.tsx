import { useEffect, useRef, useState } from "react";
import { Alert, Badge, Button, Card, Group, Stack, Text, Title } from "@mantine/core";
import {
  requestManualImport, ManualImportUnavailable,
} from "./manualImportClient";
import { planReviewedImport, REVIEWED_CLIENT_CAPABILITIES } from "./reviewedCapabilities";

/** D3g: standalone, explicitly opt-in UI. Shipping reviewed allowlist is empty.
 * Never store a subscription URL in React state, DOM attributes, localStorage,
 * query strings, analytics or logs. A QR blob URL is revoked on close/unmount.
 */
export function ManualImportPanel({
  platform, clientId, clientVersion, expectedSubscriptionOrigin,
  telegramWebView = false, pilotEnabled = false,
}: {
  platform: string; clientId: string; clientVersion: string;
  expectedSubscriptionOrigin: string;
  telegramWebView?: boolean; pilotEnabled?: boolean;
}) {
  const [qrUrl, setQrUrl] = useState("");
  const [phase, setPhase] = useState<"idle"|"working"|"success"|"error">("idle");
  const lock = useRef(false);
  const qrRef = useRef("");
  const mounted = useRef(true);
  const context = telegramWebView ? "telegram-webview" : "browser";
  const plan = planReviewedImport(platform, clientId, clientVersion,
    context, pilotEnabled, REVIEWED_CLIENT_CAPABILITIES);

  function clearQr() {
    if (qrRef.current) URL.revokeObjectURL(qrRef.current);
    qrRef.current = "";
    if (mounted.current) setQrUrl("");
  }

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (qrRef.current) URL.revokeObjectURL(qrRef.current);
      qrRef.current = "";
    };
  }, []);
  useEffect(() => {
    clearQr();
    setPhase("idle");
  }, [platform, clientId, clientVersion, telegramWebView, pilotEnabled]);

  async function act(method: "copy"|"qr") {
    if (lock.current || !pilotEnabled || plan.state === "blocked" ||
        (method === "copy" && (!plan.copy || !navigator.clipboard?.writeText)) ||
        (method === "qr" && !plan.qr)) return;
    lock.current = true;
    clearQr();
    setPhase("working");
    try {
      const value = await requestManualImport({
        platform, clientId, clientVersion, method, context,
        enabled: pilotEnabled, expectedSubscriptionOrigin,
        reviewed: REVIEWED_CLIENT_CAPABILITIES,
      }, (path, init) => window.fetch(path, init));
      if (!mounted.current) return;
      if (value.method === "copy") {
        // The bearer is scoped to this stack frame and is never displayed.
        await navigator.clipboard.writeText(value.url);
      } else {
        const objectUrl = URL.createObjectURL(value.png);
        if (!mounted.current) URL.revokeObjectURL(objectUrl);
        else {
          qrRef.current = objectUrl;
          setQrUrl(objectUrl);
        }
      }
      if (mounted.current) setPhase("success");
    } catch {
      if (mounted.current) setPhase("error");
    } finally {
      lock.current = false;
    }
  }

  return <Card withBorder radius="lg" data-testid="d3g-manual-import">
    <Stack gap="xs">
      <Group justify="space-between">
        <Title order={5}>Ручной импорт подписки</Title>
        <Badge color="gray" variant="outline">Только проверенный пилот</Badge>
      </Group>
      <Text size="sm">Клиент: {clientId || "не выбран"} · версия: {clientVersion || "не подтверждена"}</Text>
      <Text size="xs" c="dimmed">{telegramWebView
        ? "Telegram WebView: открытие приложения отключено. Только безопасный ручной Copy/QR после подтверждения."
        : "Ручной Copy/QR доступен только для проверенной версии клиента и активной подписки."}</Text>
      <Group>
        <Button disabled={plan.state === "blocked" || !plan.copy ||
            !navigator.clipboard?.writeText || phase === "working"}
          loading={phase === "working"} onClick={()=>{ void act("copy"); }}>
          Копировать ссылку
        </Button>
        <Button disabled={plan.state === "blocked" || !plan.qr || phase === "working"}
          variant="light" onClick={()=>{ void act("qr"); }}>Показать QR</Button>
      </Group>
      {qrUrl && <Stack gap="xs">
        <img src={qrUrl} alt="QR подписки — конфиденциальный код" width={220} height={220}/>
        <Button variant="subtle" onClick={clearQr}>Скрыть QR</Button>
        <Text size="xs">Не пересылайте QR: он содержит ключ доступа к VPN.</Text>
      </Stack>}
      {phase === "success" && !qrUrl && <Text size="sm" role="status">Действие выполнено.</Text>}
      {phase === "error" && <Alert color="orange" role="status">
        {new ManualImportUnavailable().message}
      </Alert>}
      {plan.state === "blocked" && <Text role="status" size="sm">
        Импорт недоступен: версия клиента ещё не подтверждена.
      </Text>}
    </Stack>
  </Card>;
}
