import React, { useState } from "react";
import {IconShieldCheck,IconLock,IconWifi,IconClock,IconDeviceMobile,IconDeviceDesktop,IconDeviceLaptop,IconDeviceTv,IconCheck,IconChevronRight,IconFileImport,IconDownload,IconSparkles,IconLink} from "@tabler/icons-react";

import { createRoot } from "react-dom/client";
import { MantineProvider, Container, Title, Text, Card, Tabs, Stack, Group, Badge, Select, Button, SegmentedControl, Divider, Accordion, Alert } from "@mantine/core";
import "@mantine/core/styles.css";
import { parsePageConfig, summary } from "./model";
import { SubscriptionPreview, previewScenarios, type PreviewScenario } from "./SubscriptionPreview";
import "./style.css";

type Localized = Record<string, string>;
type ButtonSpec = { text: Localized; link: string; type: string };
type Block = { title: Localized; description: Localized; buttons: ButtonSpec[] };
type Client = { name: string; featured?: boolean; blocks: Block[]; svgIconKey?: string };
type Platform = { apps: Client[]; displayName?: Localized };
type ExportConfig = {
  locales: string[]; version: string;
  platforms: Record<string, Platform>;
  baseSettings: { showConnectionKeys: boolean; hideGetLinkButton: boolean };
  uiConfig: { subscriptionInfoBlockType: string; installationGuidesBlockType: string };
  brandingSettings: { title?: string };
};
const sample: ExportConfig = {
  locales: ["en", "ru", "zh", "fa", "fr"], version: "1",
  platforms: {
    ios: { apps: [{name:"Демонстрационный клиент",featured:true,blocks:[
      {title:{ru:"Установить приложение"},description:{ru:"Установите совместимый VPN-клиент."},buttons:[]},
      {title:{ru:"Добавить подписку"},description:{ru:"Ссылка появится только после авторизации."},buttons:[]}
    ]}]}, android:{apps:[]},macos:{apps:[]},windows:{apps:[]},linux:{apps:[]}
  },
  baseSettings:{showConnectionKeys:false,hideGetLinkButton:false},
  uiConfig:{subscriptionInfoBlockType:"expanded",installationGuidesBlockType:"cards"},
  brandingSettings:{title:"VPN Subscription"}
};
const stateLabels:Record<string,Record<string,string>>={
 ru:{scenarioLabel:"Демонстрационные состояния",unknown:"Нет данных",active:"Активна · пример",expired:"Истекла · пример",pending:"Ожидает · пример",activeStatus:"Активна",expiredStatus:"Истекла",pendingStatus:"Ожидает подтверждения",noData:"Нет данных",daysRemaining:"15 дней · пример",demo:"ДЕМО",scenarioNote:"Вымышленные данные, не ваша подписка",usage:"Использовано",usageUnavailable:"Нет данных о трафике",previewOnly:"Без реальных подписок и ключей"},
 en:{scenarioLabel:"Demo scenarios",unknown:"No data",active:"Active · example",expired:"Expired · example",pending:"Pending · example",activeStatus:"Active",expiredStatus:"Expired",pendingStatus:"Awaiting confirmation",noData:"No data",daysRemaining:"15 days · example",demo:"DEMO",scenarioNote:"Synthetic data, not your subscription",usage:"Data used",usageUnavailable:"No usage data",previewOnly:"No real subscriptions or keys"},
 fa:{scenarioLabel:"سناریوهای نمایشی",unknown:"بدون داده",active:"فعال · نمونه",expired:"منقضی · نمونه",pending:"در انتظار · نمونه",activeStatus:"فعال",expiredStatus:"منقضی شده",pendingStatus:"در انتظار تأیید",noData:"داده‌ای موجود نیست",daysRemaining:"۱۵ روز · نمونه",demo:"نمایشی",scenarioNote:"داده آزمایشی است، نه اشتراک شما",usage:"مصرف داده",usageUnavailable:"اطلاعات مصرف موجود نیست",previewOnly:"بدون اشتراک یا کلید واقعی"},
 fr:{scenarioLabel:"Scénarios de démonstration",unknown:"Sans données",active:"Active · exemple",expired:"Expirée · exemple",pending:"En attente · exemple",activeStatus:"Active",expiredStatus:"Expirée",pendingStatus:"En attente",noData:"Aucune donnée",daysRemaining:"15 jours · exemple",demo:"DÉMO",scenarioNote:"Données fictives, pas votre abonnement",usage:"Trafic utilisé",usageUnavailable:"Trafic indisponible",previewOnly:"Aucun abonnement ni clé réels"},
 zh:{scenarioLabel:"演示场景",unknown:"无数据",active:"有效 · 示例",expired:"过期 · 示例",pending:"等待 · 示例",activeStatus:"有效",expiredStatus:"已过期",pendingStatus:"等待确认",noData:"无数据",daysRemaining:"15 天 · 示例",demo:"演示",scenarioNote:"模拟数据，并非您的订阅",usage:"已用流量",usageUnavailable:"流量数据不可用",previewOnly:"不提供真实订阅或密钥"}
};
const platformNames: Record<string,string> = {ios:"iOS",android:"Android",macos:"macOS",windows:"Windows",linux:"Linux",appleTV:"Apple TV",androidTV:"Android TV"};
function languageText(v: Localized | undefined, lang:string) {return v?.[lang] ?? v?.ru ?? v?.en ?? "";}
function App() {
  const [data,setData] = useState<ExportConfig>(sample);
  const [lang,setLang] = useState("ru");
  const platforms = Object.keys(data.platforms);
  const [platform,setPlatform] = useState(platforms[0] || "ios");
  const [client,setClient] = useState(0);
  const [view,setView] = useState("cards");
  const [info,setInfo] = useState("expanded");
  const [scenario,setScenario] = useState<PreviewScenario>("unknown");
  const [error,setError] = useState("");
  const [imported,setImported] = useState(false);
  const selected = data.platforms[platform]?.apps[client];
  function openLocalFile(file: File | null) {
    if (!file) return;
    if (file.size > 1024*1024) { setError("Файл превышает 1 МиБ"); return; }
    file.text().then(raw => {try {
      const cfg: ExportConfig = parsePageConfig(raw);
      setData(cfg);setLang(cfg.locales.includes("ru")?"ru":cfg.locales[0]);setPlatform(Object.keys(cfg.platforms)[0]);setClient(0);setView(cfg.uiConfig.installationGuidesBlockType);setInfo(cfg.uiConfig.subscriptionInfoBlockType);setImported(true);setError("");
    } catch { setError("Неверный формат локальной конфигурации"); }});
  }
  const ui:Record<string,Record<string,string>>={
    ru:{hero:"Безопасный интернет.",hero2:"Без лишних сложностей.",lead:"Ваше подключение — под контролем. Выберите устройство и следуйте простым шагам.",preview:"Демонстрационный режим",subscription:"Моя подписка",status:"Статус",noData:"Нет данных",traffic:"Трафик",expires:"Срок действия",connect:"Подключить VPN",device:"Выберите устройство",application:"Выберите приложение",steps:"Следуйте инструкции",safe:"Безопасный предпросмотр",safeDesc:"Никакие реальные подписки и ключи не выдаются. Всё работает локально в браузере.",import:"Импортировать настройки",noClients:"Для этой платформы нет настроенных клиентов.",hide:"Блок подписки скрыт настройкой предпросмотра.",keys:"Ключи не выдаются в режиме предпросмотра",footer:"Демонстрационная версия · Без выдачи ключей и реальных подписок"},
    en:{hero:"A safer internet.",hero2:"Without the complexity.",lead:"Your connection, under control. Choose your device and follow the steps.",preview:"Preview mode",subscription:"My subscription",status:"Status",noData:"No data",traffic:"Traffic",expires:"Expires",connect:"Connect your VPN",device:"Choose device",application:"Choose application",steps:"Follow instructions",safe:"Safe preview",safeDesc:"No live subscriptions or keys are provided. Everything remains in your browser.",import:"Import configuration",noClients:"No apps configured for this platform.",hide:"Subscription block is hidden in preview.",keys:"Keys are unavailable in preview",footer:"Preview · No real subscriptions or keys"},
    fa:{hero:"اینترنت امن‌تر.",hero2:"بدون پیچیدگی.",lead:"اتصال شما تحت کنترل است. دستگاه خود را انتخاب کنید.",preview:"حالت پیش‌نمایش",subscription:"اشتراک من",status:"وضعیت",noData:"داده‌ای موجود نیست",traffic:"ترافیک",expires:"انقضا",connect:"اتصال به VPN",device:"انتخاب دستگاه",application:"انتخاب برنامه",steps:"مراحل اتصال",safe:"پیش‌نمایش امن",safeDesc:"اشتراک واقعی و کلید نمایش داده نمی‌شود. همه چیز در مرورگر شما می‌ماند.",import:"وارد کردن تنظیمات",noClients:"برنامه‌ای برای این پلتفرم تنظیم نشده است.",hide:"بخش اشتراک پنهان شده است.",keys:"کلیدها در پیش‌نمایش در دسترس نیستند",footer:"نسخه آزمایشی · بدون اشتراک واقعی"}
  };
  const t=(x:string)=>stateLabels[lang]?.[x]??ui[lang]?.[x]??ui.en[x]??x;
  const deviceIcon=(x:string)=>x==="ios"||x==="android"?<IconDeviceMobile size={21}/>:x==="macos"?<IconDeviceLaptop size={21}/>:x.toLowerCase().includes("tv")?<IconDeviceTv size={21}/>:<IconDeviceDesktop size={21}/>;
  const steps=selected?.blocks??[];
  return <MantineProvider defaultColorScheme="dark" theme={{primaryColor:"blue"}}>
  <div className="portal-shell" dir={lang==="fa"?"rtl":"ltr"}><Container className="portal-container" size={1120}>
    <header className="portal-header">
      <div className="portal-logo"><span className="brand-square"><img src="/brand/raccoon-wrench.svg" alt=""/></span><span><strong>RACCOON <em>VPN</em></strong><small>YOUR SECURE CONNECTION</small></span></div>
      <div className="header-right"><Badge leftSection={<IconShieldCheck size={13}/>} variant="light" color="blue">{t("safe")}</Badge><Select aria-label="Language" value={lang} onChange={x=>setLang(x||"ru")} data={data.locales.map(x=>({value:x,label:x.toUpperCase()}))} w={88}/></div>
    </header>
    <main>
      <section className="hero"><div className="hero-content"><div className="hero-pill"><IconSparkles size={15}/>{t("preview")}</div><h1>{t("hero")}<br/><span>{t("hero2")}</span></h1><p>{t("lead")}</p><div className="hero-safe"><IconLock size={16}/>{t("safeDesc")}</div></div><div className="hero-art" aria-hidden="true"><div className="hero-halo"/><img src="/brand/raccoon-wrench.svg" alt=""/></div></section>
      <section className="portal-section" aria-label={t("subscription")}><div className="section-heading"><div><span className="section-eyebrow">01 — SUBSCRIPTION</span><Title order={2}>{t("subscription")}</Title></div><SegmentedControl aria-label="Вид блока подписки" data-testid="subscription-layout" value={info} onChange={setInfo} size="xs" data={["expanded","collapsed","cards","hidden"]}/></div>
        <div className="scenario-controls"><Text size="xs" c="dimmed">{t("scenarioLabel")}</Text><SegmentedControl data-testid="subscription-scenario" aria-label={t("scenarioLabel")} value={scenario} onChange={v=>setScenario(v as PreviewScenario)} size="xs" data={previewScenarios.map(v=>({value:v,label:t(v)}))}/></div>
        <SubscriptionPreview mode={info} scenario={scenario} t={t} hideGetLinkButton={data.baseSettings.hideGetLinkButton} showConnectionKeys={data.baseSettings.showConnectionKeys}/>
      </section>
      <section className="portal-section" aria-label={t("connect")}><div className="section-heading"><div><span className="section-eyebrow">02 — QUICK START</span><Title order={2}>{t("connect")}</Title></div><SegmentedControl aria-label="Вид инструкций" data-testid="guides-layout" data={["cards","timeline","accordion","minimal"].map(x=>({label:x,value:x}))} size="xs" value={view} onChange={setView}/></div>
        <div className="setup-shell"><div className="setup-segment"><div className="setup-title"><span>01</span><strong>{t("device")}</strong></div><Tabs value={platform} onChange={x=>{if(x){setPlatform(x);setClient(0);}}}><Tabs.List className="device-tabs">{platforms.map(x=><Tabs.Tab key={x} value={x} leftSection={deviceIcon(x)}>{languageText(data.platforms[x]?.displayName,lang)||platformNames[x]||x}</Tabs.Tab>)}</Tabs.List></Tabs></div>
          <div className="setup-segment"><div className="setup-title"><span>02</span><strong>{t("application")}</strong></div><div className="client-list">{data.platforms[platform]?.apps.map((a,i)=><button type="button" key={i} className={"client-choice "+(i===client?"active":"")} onClick={()=>setClient(i)}><span className="client-icon"><IconDeviceMobile size={22}/></span><span className="client-copy"><strong>{a.name}</strong>{a.featured&&<small><IconCheck size={13}/> {t("preview")}</small>}</span>{i===client?<IconCheck size={18}/>:<IconChevronRight size={18}/>}</button>)}</div>{!data.platforms[platform]?.apps.length&&<Text c="dimmed">{t("noClients")}</Text>}</div>
          <div className="setup-segment"><div className="setup-title"><span>03</span><strong>{t("steps")}</strong></div>{selected?(view==="accordion"?<Accordion multiple variant="separated" defaultValue={steps.map((_,i)=>String(i))}>{steps.map((bl,i)=><Accordion.Item key={i} value={String(i)}><Accordion.Control>{i+1}. {languageText(bl.title,lang)}</Accordion.Control><Accordion.Panel><Text className="step-text">{languageText(bl.description,lang)}</Text><Group mt="md">{bl.buttons?.map((bt,j)=><Button key={j} disabled color="blue">{languageText(bt.text,lang)}</Button>)}</Group></Accordion.Panel></Accordion.Item>)}</Accordion>:<Stack className={view==="timeline"?"timeline-list":view==="minimal"?"minimal-list":"cards-list"}>{steps.map((bl,i)=><Card key={i} radius="lg" className="step-card" withBorder={view!=="minimal"}><div className="step-row"><span className="step-number">{String(i+1).padStart(2,"0")}</span><div><Title order={5}>{i+1}. {languageText(bl.title,lang)}</Title><Text mt="xs" className="step-text">{languageText(bl.description,lang)}</Text><Group mt="md">{bl.buttons?.map((bt,j)=><Button key={j} disabled color="blue">{languageText(bt.text,lang)}</Button>)}</Group></div></div></Card>)}</Stack>):<Text c="dimmed">{t("noClients")}</Text>}</div></div>
      </section>
      <section className="bottom-panels"><div className="safe-panel"><span><IconShieldCheck size={26}/></span><div><Title order={4}>{t("safe")}</Title><Text c="dimmed" size="sm">{t("safeDesc")}</Text></div></div><div className="import-panel"><div><Text fw={800}><IconFileImport size={19}/> {t("import")}</Text><Text c="dimmed" size="xs">{t("preview")}</Text></div><label className="file-pick"><IconDownload size={16}/> JSON<input aria-label={t("import")} type="file" accept=".json,application/json" onChange={e=>openLocalFile(e.target.files?.[0]||null)}/></label></div></section>
      {error&&<Alert mt="lg" color="red">{error}</Alert>}{imported&&<Text mt="md" c="blue">{t("import")}: {summary(data as any).blocks}</Text>}
    </main><footer className="portal-footer"><span><img src="/brand/raccoon-wrench.svg" alt=""/> RACCOON VPN</span><Text size="xs">{t("footer")}</Text></footer>
  </Container></div></MantineProvider>;
}
createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
