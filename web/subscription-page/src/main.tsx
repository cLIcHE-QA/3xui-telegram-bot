import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { MantineProvider, Container, Title, Text, Card, Tabs, Stack, Group, Badge, Select, Button, SegmentedControl, Divider } from "@mantine/core";
import "@mantine/core/styles.css";
import { parsePageConfig } from "./model";
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
  const selected = data.platforms[platform]?.apps[client];
  function openLocalFile(file: File | null) {
    if (!file || file.size > 1024*1024) return;
    file.text().then(raw => {try {
      const cfg: ExportConfig = parsePageConfig(raw);
      setData(cfg);setLang(cfg.locales.includes("ru")?"ru":cfg.locales[0]);setPlatform(Object.keys(cfg.platforms)[0]);setClient(0);
    } catch { alert("Неверный формат локальной конфигурации"); }});
  }
  return <MantineProvider defaultColorScheme="dark">
    <Container size="lg" py="xl">
      <Stack gap="xl">
        <Group justify="space-between" align="start">
          <div><Title order={2}>{data.brandingSettings?.title || "Subscription"}</Title><Text c="dimmed">Демонстрационная страница — без данных подписки · импорт из локального JSON, без сети</Text></div>
          <Select aria-label="Language" value={lang} onChange={x=>setLang(x||"ru")} data={data.locales.map(x=>({value:x,label:x.toUpperCase()}))} w={100} />
        </Group>
        <Card withBorder radius="lg" padding="lg">
          <Group justify="space-between"><Title order={4}>Моя подписка</Title><Badge color="gray">Нет данных</Badge></Group>
          <Text c="dimmed" size="sm" mt="sm">Статус, трафик и ключи появятся после защищённого подключения к Python backend. Сейчас показываются только демонстрационные данные.</Text>
        </Card>
        <Card withBorder radius="lg" padding="lg">
          <Stack>
            <Group justify="space-between"><Title order={3}>Установка VPN</Title><SegmentedControl data={["cards","timeline","accordion","minimal"].map(x=>({label:x,value:x}))} size="xs" value={view} onChange={setView}/></Group>
            <Tabs value={platform} onChange={x=>{if(x){setPlatform(x);setClient(0);}}}>
              <Tabs.List>{platforms.map(x=><Tabs.Tab key={x} value={x}>{platformNames[x]||x}</Tabs.Tab>)}</Tabs.List>
            </Tabs>
            <Group>{data.platforms[platform]?.apps.map((a,i)=><Button key={i} color={i===client?"teal":"gray"} variant={i===client?"filled":"light"} onClick={()=>setClient(i)}>{a.name}{a.featured?" ★":""}</Button>)}</Group>
            {selected ? <Stack>{selected.blocks.map((bl,i)=><Card key={i} radius="md" className="step-card" withBorder>
              <Group justify="space-between"><Title order={5}>{i+1}. {languageText(bl.title,lang)}</Title><Badge variant="outline">{view}</Badge></Group>
              <Text mt="sm">{languageText(bl.description,lang)}</Text>
              {bl.buttons?.length>0 && <Group mt="md">{bl.buttons.map((bt,j)=><Button key={j} disabled title="Безопасный демонстрационный режим: внешние ссылки и глубокий импорт отключены">{languageText(bt.text,lang)}</Button>)}</Group>}
            </Card>)}</Stack>:<Text c="dimmed">Для этой платформы нет настроенных клиентов.</Text>}
          </Stack>
        </Card>
        <Divider />
        <Text c="dimmed" size="xs">D1a local preview: внешние URL, импорт подписок, raw keys и админские функции отключены. Этот build не является клиентским кабинетом.</Text>
        <label className="file-pick">Открыть свой JSON локально (ничего не отправляется на сервер): <input type="file" accept=".json,application/json" onChange={e=>openLocalFile(e.target.files?.[0]||null)}/></label>
      </Stack>
    </Container>
  </MantineProvider>;
}
createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
