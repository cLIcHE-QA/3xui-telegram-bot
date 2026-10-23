import { Alert, Badge, Button, Card, Progress, Text, Title } from "@mantine/core";
import { IconAlertCircle, IconCheck, IconClock, IconDeviceMobile, IconLink, IconLock, IconShieldCheck, IconWifi } from "@tabler/icons-react";

export type PreviewScenario = "unknown" | "active" | "expired" | "pending";
export const previewScenarios: PreviewScenario[] = ["unknown", "active", "expired", "pending"];

type Props = {
  mode: string;
  scenario: PreviewScenario;
  t: (key: string) => string;
  hideGetLinkButton: boolean;
  showConnectionKeys: boolean;
};

function snapshot(scenario: PreviewScenario, t: Props["t"]) {
  switch (scenario) {
    case "active":
      return { status: t("activeStatus"), traffic: "24.6 / 100 GB", expiry: t("daysRemaining"), percent: 24.6, tone: "active" };
    case "expired":
      return { status: t("expiredStatus"), traffic: "—", expiry: t("expiredStatus"), percent: null, tone: "expired" };
    case "pending":
      return { status: t("pendingStatus"), traffic: "—", expiry: "—", percent: null, tone: "pending" };
    default:
      return { status: t("noData"), traffic: "—", expiry: "—", percent: null, tone: "unknown" };
  }
}

/**
 * Visual fixtures only. No subscription API, bearer URL, key, or network request.
 * Every state is synthetic and must remain visibly marked as such.
 */
export function SubscriptionPreview({ mode, scenario, t, hideGetLinkButton, showConnectionKeys }: Props) {
  const data = snapshot(scenario, t);
  const metrics = [
    { label: t("status"), value: data.status, icon: <IconShieldCheck size={20} /> },
    { label: t("traffic"), value: data.traffic, icon: <IconWifi size={20} /> },
    { label: t("expires"), value: data.expiry, icon: <IconClock size={20} /> },
  ];

  return <div data-testid="subscription-preview" data-mode={mode} data-scenario={scenario}>
    {mode === "hidden" ? (
      <div className="hidden-subscription"><IconLock size={20} /><span>{t("hide")}</span></div>
    ) : (
      <>
        {mode === "cards" ? (
          <div className="subscription-info-grid">
            {metrics.map(({ label, value, icon }) => (
              <Card key={label} className="metric-card" withBorder radius="lg" padding="lg">
                <div className="metric-card-head"><span className="metric-icon">{icon}</span><Badge variant="outline" color="gray" size="xs">{t("demo")}</Badge></div>
                <Text c="dimmed" size="sm">{label}</Text>
                <Text size="lg" fw={800} mt="sm">{value}</Text>
              </Card>
            ))}
          </div>
        ) : mode === "collapsed" ? (
          <Card className="subscription-info-compact" withBorder radius="xl" padding="lg">
            <div className="compact-status"><span className={"status-orb " + data.tone}><IconShieldCheck size={25}/></span><div className="compact-copy"><Text size="xs" c="dimmed">{t("subscription")}</Text><Text fw={800}>{data.status}</Text></div><Badge color="gray" variant="light">{t("demo")}</Badge></div>
          </Card>
        ) : (
          <Card withBorder radius="xl" padding={0} className={"subscription-main-card scenario-" + data.tone}>
            <div className="subscription-topline">
              <div className="subscription-topline-caption"><IconShieldCheck size={17}/>{t("subscriptionLead")}</div>
              <Badge color="blue" variant="light">{t("demo")}</Badge>
            </div>
            <div className="subscription-body">
              <div className="subscription-status">
                <span className={"status-orb " + data.tone}>{scenario === "expired" ? <IconAlertCircle size={32}/> : scenario === "active" ? <IconCheck size={32}/> : <IconShieldCheck size={32}/>}</span>
                <div><Text size="xs" c="dimmed">{t("status")}</Text><Title order={3}>{data.status}</Title><Text size="xs" className="subscription-fixture-note">{t("scenarioNote")}</Text></div>
              </div>
              <div className="subscription-metrics">
                <div><Text size="xs" c="dimmed">{t("traffic")}</Text><strong>{data.traffic}</strong></div>
                <div><Text size="xs" c="dimmed">{t("expires")}</Text><strong>{data.expiry}</strong></div>
              </div>
            </div>
            <div className="subscription-bottom">
              <div className="subscription-progress-title"><span><IconWifi size={15}/>{t("usage")}</span><span>{data.percent === null ? t("notAvailable") : "24.6%"}</span></div>
              {data.percent === null ? <div className="subscription-progress-empty" aria-label={t("usageUnavailable")}/> : <Progress aria-label={t("usage")} value={data.percent} size="sm" radius="xl" color="cyan"/>}
              <Text size="xs" className="subscription-progress-note"><IconDeviceMobile size={14}/>{t("previewOnly")}</Text>
            </div>
          </Card>
        )}
        <div className="sub-actions">
          {!hideGetLinkButton && <Button disabled leftSection={<IconLink size={18}/>} variant="filled" color="blue">{t("getLink")}</Button>}
          {showConnectionKeys && <Alert icon={<IconLock size={17}/>} color="yellow" className="keys-preview-alert">{t("keys")}</Alert>}
          <Text className="preview-under-action" size="xs"><IconLock size={13}/>{t("previewOnly")}</Text>
        </div>
      </>
    )}
  </div>;
}
