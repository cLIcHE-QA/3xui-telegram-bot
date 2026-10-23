import { useEffect, useState } from "react";
import { Accordion, Badge, Button, Card, Text, Title } from "@mantine/core";
import { IconChevronLeft, IconChevronRight, IconCircleCheck, IconDownload, IconInfoCircle, IconLink, IconLock, IconShieldCheck } from "@tabler/icons-react";

type Localized = Record<string, string>;
type Action = { text: Localized; link: string; type: string };
type Step = { title: Localized; description: Localized; buttons: Action[] };
type Props = { steps: Step[]; mode: string; lang: string; t: (key: string) => string; clientName?: string };

const translate = (value: Localized | undefined, lang: string): string =>
  value?.[lang] ?? value?.en ?? value?.ru ?? "";

function GuideActions({ actions, lang, t }: { actions: Action[]; lang: string; t: Props["t"] }) {
  return <div className="guide-actions">
    {actions.map((action, i) => <Button key={i} disabled size="xs" variant="light"
      leftSection={action.type === "subscriptionLink" ? <IconLink size={14}/> : <IconDownload size={14}/>}>
      {translate(action.text, lang)}
    </Button>)}
    <span className="guide-action-caption"><IconLock size={14} aria-hidden="true"/>{t("guideActionsLocked")}</span>
  </div>;
}

function StepBody({ step, lang, t }: { step: Step; lang: string; t: Props["t"] }) {
  return <>
    <Text className="guide-description">{translate(step.description, lang)}</Text>
    <GuideActions actions={step.buttons ?? []} lang={lang} t={t}/>
  </>;
}

/** Visual-only guide: input JSON URLs and icons are never opened, copied or rendered as HTML. */
export function ConnectionGuide({ steps, mode, lang, t, clientName }: Props) {
  const [stepIndex,setStepIndex]=useState(0);
  useEffect(()=>setStepIndex(0),[steps,clientName,mode]);
  const active=Math.min(stepIndex,Math.max(0,steps.length-1));

  if (!steps.length) {
    return <div data-testid="guide-preview" data-mode={mode} className="guide-empty" role="status">
      <span className="guide-empty-icon"><IconInfoCircle size={26}/></span>
      <div><strong>{t("guideEmptyTitle")}</strong><Text size="sm">{t("guideEmptyText")}</Text></div>
    </div>;
  }

  return <div data-testid="guide-preview" data-mode={mode} className={"connection-guide mode-" + mode}>
    <div className="guide-header">
      <span className="guide-header-mark"><IconShieldCheck size={18} aria-hidden="true"/>{t("guideHeader")}</span>
      <Badge variant="outline" color="blue">{t("demo")}</Badge>
      <span className="guide-header-count">{t("guideStepsLabel")}: {steps.length}</span>
    </div>
    {clientName && <Text className="guide-client-name" size="sm">{t("guideForClient")}: <strong>{clientName}</strong></Text>}
    {mode === "carousel" ? <div className="guide-carousel" data-testid="guide-carousel" data-active-index={active}>
      <div className="guide-carousel-progress" role="group" aria-label={t("guideNavigation")}>
        {steps.map((step,i)=><button type="button" key={i} className="guide-carousel-dot" aria-current={active===i?"step":undefined}
          aria-label={t("guideStepLabel")+" "+(i+1)+": "+translate(step.title,lang)} onClick={()=>setStepIndex(i)}>{i+1}</button>)}
      </div>
      <Card className="guide-carousel-card" withBorder radius="lg" padding="lg">
        <div className="guide-carousel-step-head"><Text fw={700} size="sm">{t("guideStepLabel")} {active+1} {t("guideOf")} {steps.length}</Text><IconShieldCheck size={19}/></div>
        <Title order={5} className="guide-step-title">{translate(steps[active].title,lang)}</Title>
        <StepBody step={steps[active]} lang={lang} t={t}/>
      </Card>
      <nav className="guide-carousel-controls" aria-label={t("guideNavigation")}>
        <Button data-testid="guide-previous" variant="default" disabled={active===0}
          leftSection={<IconChevronLeft size={17}/>} onClick={()=>setStepIndex(i=>Math.max(0,i-1))}>{t("guidePrevious")}</Button>
        <Button data-testid="guide-next" disabled={active===steps.length-1}
          rightSection={<IconChevronRight size={17}/>} onClick={()=>setStepIndex(i=>Math.min(steps.length-1,i+1))}>{t("guideNext")}</Button>
      </nav>
    </div> : mode === "accordion" ? (
      <Accordion key={clientName} className="guide-accordion" variant="separated" radius="md" defaultValue="0">
        {steps.map((step,i) => <Accordion.Item key={i} value={String(i)}>
          <Accordion.Control icon={<span className="guide-index">{String(i + 1).padStart(2, "0")}</span>}>
            <span className="guide-accordion-label">{translate(step.title, lang)}</span>
          </Accordion.Control>
          <Accordion.Panel><StepBody step={step} lang={lang} t={t}/></Accordion.Panel>
        </Accordion.Item>)}
      </Accordion>
    ) : (
      <div className={"guide-step-grid guide-" + mode}>
        {steps.map((step,i) => <Card key={i} className="guide-step" padding={mode === "minimal" ? "sm" : "lg"} radius="lg" withBorder={mode !== "minimal"}>
          <div className="guide-step-top">
            <span className="guide-index">{String(i + 1).padStart(2,"0")}</span>
            <span className="guide-step-symbol" aria-hidden="true">{i === 0 ? <IconDownload size={18}/> : i === steps.length - 1 ? <IconCircleCheck size={18}/> : <IconChevronRight size={18}/>}</span>
          </div>
          <Title order={5} className="guide-step-title">{translate(step.title,lang)}</Title>
          <StepBody step={step} lang={lang} t={t}/>
        </Card>)}
      </div>
    )}
    <div className="guide-footnote"><IconLock size={16} aria-hidden="true"/>{t("guideFootnote")}</div>
  </div>;
}
