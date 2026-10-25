import { Badge, Card, Group, Stack, Text, Title } from "@mantine/core";
import { planClientImport, type ImportCapability } from "./importPlanner";

/**
 * #887 D3b: presentation-only preview; never receives a subscription URL.
 * No anchor, copy handler, QR encoding or custom-scheme invocation is possible.
 */
export function ImportCapabilityPreview({
  platform, client, telegramWebView = false, pilotEnabled = false,
}: {platform: string; client: string; telegramWebView?: boolean; pilotEnabled?: boolean}) {
  // Imported JSON is untrusted and cannot attest to app/version support.
  const capability: ImportCapability = {
    platform, client, verified: false,
    supportsHandoff: false, supportsCopy: false, supportsQr: false,
  };
  const plan = planClientImport(capability, telegramWebView ? "telegram-webview" : "browser", pilotEnabled);
  return <Card withBorder radius="lg" data-testid="d3b-import-preview" aria-label="Импорт VPN — предварительная проверка">
    <Stack gap="xs">
      <Group justify="space-between">
        <Title order={5}>Импорт в VPN-клиент</Title>
        <Badge color="gray" variant="outline">D3b · предпросмотр</Badge>
      </Group>
      <Text size="sm">Платформа: {platform || "не выбрана"} · Клиент: {client || "не выбран"}</Text>
      <Text size="sm" role="status">{plan.state === "blocked"
        ? "Импорт недоступен: совместимость клиента и версия не подтверждены."
        : "Ручной импорт доступен только после отдельной проверки клиента и разрешения пилота."}</Text>
      <Text size="xs" c="dimmed">Copy, QR и открытие приложения отключены. Реальная ссылка подписки не используется. Telegram WebView требует отдельного device smoke.</Text>
    </Stack>
  </Card>;
}
