import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { MantineProvider, Container, Title, Text, Card, Tabs, Stack, Group, Badge, Select, Button, SegmentedControl, Divider, Accordion, Alert } from "@mantine/core";
import "@mantine/core/styles.css";
import { parsePageConfig, summary } from "./model";
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
  return <MantineProvider defaultColorScheme="dark">
    <div dir={lang==="fa"?"rtl":"ltr"}><Container size="lg" py="xl">
      <Stack gap="xl">
        <Group justify="space-between" align="start">
          <div><Title order={2}>{data.brandingSettings?.title || "Subscription"}</Title><Text c="dimmed">Демонстрационная страница — без данных подписки · импорт из локального JSON, без сети</Text></div>
          <Select aria-label="Language" value={lang} onChange={x=>setLang(x||"ru")} data={data.locales.map(x=>({value:x,label:x.toUpperCase()}))} w={100} />
        </Group>
        <Group justify="space-between"><Title order={4}>Моя подписка</Title><SegmentedControl aria-label="Вид блока подписки" data-testid="subscription-layout" value={info} onChange={setInfo} size="xs" data={["expanded","collapsed","cards","hidden"]}/></Group>
        <div data-testid="subscription-preview" data-mode={info}>
          {info==="hidden" ? <Text c="dimmed" size="sm">Блок подписки скрыт настройкой предпросмотра.</Text> :
            <>
              {info==="cards" ? <div className="subscription-info-grid">
                {[["Статус","Нет данных"],["Трафик","—"],["Срок","—"]].map(([heading,value])=><Card key={heading} withBorder radius="lg" padding="md"><Text size="xs" c="dimmed">{heading}</Text><Text fw={600} mt="xs">{value}</Text></Card>)}
              </div> : info==="collapsed" ? <Card withBorder radius="lg" padding="md" className="subscription-info-compact">
                <Group justify="space-between" align="center"><Text fw={600}>Моя подписка</Text><Badge color="gray">Нет данных</Badge></Group>
              </Card> : <Card withBorder radius="lg" padding="lg">
                <Group justify="space-between"><Title order={4}>Моя подписка</Title><Badge color="gray">Нет данных</Badge></Group>
                <Text c="dimmed" size="sm" mt="sm">Статус — · Трафик — · Срок —</Text>
              </Card>}
              {!data.baseSettings.hideGetLinkButton&&<Button mt="md" disabled variant="light">Get Link</Button>}
              {data.baseSettings.showConnectionKeys&&<Alert color="yellow" mt="md">Ключи не выдаются в режиме предпросмотра</Alert>}
            </>}
        </div>
        <Card withBorder radius="lg" padding="lg">
          <Stack>
            <Group justify="space-between"><Title order={3}>Установка VPN</Title><SegmentedControl aria-label="Вид инструкций" data-testid="guides-layout" data={["cards","timeline","accordion","minimal"].map(x=>({label:x,value:x}))} size="xs" value={view} onChange={setView}/></Group>
            <Tabs value={platform} onChange={x=>{if(x){setPlatform(x);setClient(0);}}}>
              <Tabs.List>{platforms.map(x=><Tabs.Tab key={x} value={x}>{languageText(data.platforms[x]?.displayName,lang)||platformNames[x]||x}</Tabs.Tab>)}</Tabs.List>
            </Tabs>
            <Group>{data.platforms[platform]?.apps.map((a,i)=><Button key={i} color={i===client?"teal":"gray"} variant={i===client?"filled":"light"} onClick={()=>setClient(i)}>{a.name}{a.featured?" ★":""}</Button>)}</Group>
            {selected ? (view==="accordion" ? <Accordion multiple variant="separated">{selected.blocks.map((bl,i)=><Accordion.Item key={i} value={String(i)}><Accordion.Control>{i+1}. {languageText(bl.title,lang)}</Accordion.Control><Accordion.Panel><Text className="step-text">{languageText(bl.description,lang)}</Text><Group mt="md">{bl.buttons?.map((bt,j)=><Button key={j} disabled color="teal">{languageText(bt.text,lang)}</Button>)}</Group></Accordion.Panel></Accordion.Item>)}</Accordion> : <Stack className={view==="timeline"?"timeline-list":view==="minimal"?"minimal-list":""}>{selected.blocks.map((bl,i)=><Card key={i} radius="md" className="step-card" withBorder={view!=="minimal"}><Title order={5}>{i+1}. {languageText(bl.title,lang)}</Title><Text mt="sm" className="step-text">{languageText(bl.description,lang)}</Text><Group mt="md">{bl.buttons?.map((bt,j)=><Button key={j} disabled color="teal">{languageText(bt.text,lang)}</Button>)}</Group></Card>)}</Stack>) : <Text c="dimmed">Для этой платформы нет настроенных клиентов.</Text>}
          </Stack>
        </Card>
        <Divider />
        {error&&<Alert color="red">{error}</Alert>}
        {imported&&<Text c="teal">JSON загружен локально: {summary(data as any).blocks} шагов</Text>}
        <Text c="dimmed" size="xs">D1a local preview: внешние URL, импорт подписок, raw keys и админские функции отключены. Этот build не является клиентским кабинетом.</Text>
        <label className="file-pick">Открыть свой JSON локально (ничего не отправляется на сервер): <input type="file" accept=".json,application/json" onChange={e=>openLocalFile(e.target.files?.[0]||null)}/></label>
      </Stack>
    </Container></div>
  </MantineProvider>;
}
createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
