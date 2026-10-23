import { Alert, Badge, Button, Card, Progress, Text, Title } from "@mantine/core";
import { IconAlertCircle, IconCalendar, IconCheck, IconClock, IconCreditCard, IconDeviceMobile, IconLink, IconLock, IconRefresh, IconShieldCheck, IconWifi } from "@tabler/icons-react";

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
  const missing = t("notAvailable");
  switch (scenario) {
    case "active":
      return { status: t("activeStatus"), traffic: "24.6 / 100 GB", expiry: t("daysRemaining"), plan: t("planUnknown"),
        reset: t("resetUnknown"), percent: 24.6, tone: "active" as const };
    case "expired":
      return { status: t("expiredStatus"), traffic: missing, expiry: t("expiredStatus"), plan: t("planUnknown"),
        reset: t("resetUnknown"), percent: null, tone: "expired" as const };
    case "pending":
      return { status: t("pendingStatus"), traffic: missing, expiry: missing, plan: t("planUnknown"),
        reset: t("resetUnknown"), percent: null, tone: "pending" as const };
    default:
      return { status: t("noData"), traffic: missing, expiry: missing, plan: t("planUnknown"),
        reset: t("resetUnknown"), percent: null, tone: "unknown" as const };
  }
}

/**
 * Synthetic presentation data only. Never authenticate with, issue or expose a
 * subscription URL. Unknown plan/reset/expiry must not appear as confirmed facts.
 */
export function SubscriptionPreview({ mode, scenario, t, hideGetLinkButton, showConnectionKeys }: Props) {
  const data = snapshot(scenario, t);
  const metrics = [
    { id: "plan", label: t("planLabel"), value: data.plan, color: "blue", icon: <IconCreditCard size={19} /> },
    { id: "status", label: t("status"), value: data.status, color: data.tone, icon: data.tone === "expired"
      ? <IconAlertCircle size={19} /> : data.tone === "active" ? <IconCheck size={19} /> : <IconShieldCheck size={19} /> },
    { id: "traffic", label: t("traffic"), value: data.traffic, color: "amber", icon: <IconWifi size={19} /> },
    { id: "expiry", label: t("expires"), value: data.expiry, color: data.tone === "expired" ? "expired" : "rose",
      icon: <IconCalendar size={19} /> },
  ];

  const renderTile = (metric: typeof metrics[number]) => <div key={metric.id}
    className={"subscription-stat-tile stat-" + metric.color} data-testid={"subscription-tile-" + metric.id}>
    <div className="subscription-stat-head">
      <span className="subscription-stat-icon" aria-hidden="true">{metric.icon}</span>
      <span className="subscription-stat-label">{metric.label}</span>
    </div>
    <strong className="subscription-stat-value">{metric.value}</strong>
  </div>;

  const safeActions = <div className="sub-actions">
    {!hideGetLinkButton && <Button disabled leftSection={<IconLink size={18}/>} variant="filled" color="blue">{t("getLink")}</Button>}
    {showConnectionKeys && <Alert icon={<IconLock size={17}/>} color="yellow" className="keys-preview-alert">{t("keys")}</Alert>}
    <Text className="preview-under-action" size="xs"><IconLock size={13}/>{t("previewOnly")}</Text>
  </div>;

  return <div data-testid="subscription-preview" data-mode={mode} data-scenario={scenario}>
    {mode === "hidden" ? (
      <div className="hidden-subscription"><IconLock size={20} /><span>{t("hide")}</span></div>
    ) : <>
      {mode === "cards" ? (
        <div className="subscription-info-grid">
          {metrics.map(metric => <Card key={metric.id} className="metric-card subscription-standalone-tile"
            withBorder radius="lg" padding="sm">{renderTile(metric)}</Card>)}
        </div>
      ) : mode === "collapsed" ? (
        <Card className="subscription-info-compact" withBorder radius="xl" padding="lg">
          <div className="compact-status">
            <span className={"status-orb " + data.tone}><IconShieldCheck size={25}/></span>
            <div className="compact-copy"><Text size="xs" c="dimmed">{t("subscription")}</Text><Text fw={800}>{data.status}</Text></div>
            <Badge color="blue" variant="light">{t("demo")}</Badge>
          </div>
        </Card>
      ) : (
        <Card withBorder radius="xl" padding={0} className={"subscription-main-card subscription-highlight-card scenario-" + data.tone}>
          <div className="subscription-topline">
            <div className="subscription-topline-caption"><IconShieldCheck size={17}/>{t("subscriptionLead")}</div>
            <Badge color="blue" variant="light">{t("demo")}</Badge>
          </div>
          <div className="subscription-summary">
            <span className={"status-orb " + data.tone} aria-hidden="true">{data.tone === "expired"
              ? <IconAlertCircle size={25}/> : data.tone === "active" ? <IconCheck size={25}/> : <IconShieldCheck size={25}/>}</span>
            <div className="subscription-summary-copy">
              <Title order={3}>{t("subscription")}</Title>
              <Text size="xs" className="subscription-fixture-note">{t("scenarioNote")}</Text>
            </div>
          </div>
          <div className="subscription-stat-grid">{metrics.map(renderTile)}</div>
          <div className="subscription-bottom">
            <div className="subscription-progress-title"><span><IconWifi size={15}/>{t("usage")}</span>
              <span>{data.percent === null ? t("notAvailable") : "24.6%"}</span></div>
            {data.percent === null
              ? <div className="subscription-progress-empty" aria-label={t("usageUnavailable")}/>
              : <Progress aria-label={t("usage")} value={data.percent} size="sm" radius="xl" color="cyan"/>}
            <div className="subscription-reset"><IconRefresh size={15} aria-hidden="true"/>
              <span>{t("resetLabel")}: <strong>{data.reset}</strong></span></div>
            <Text size="xs" className="subscription-progress-note"><IconDeviceMobile size={14}/>{t("previewOnly")}</Text>
          </div>
        </Card>
      )}
      {safeActions}
    </>}
  </div>;
}
