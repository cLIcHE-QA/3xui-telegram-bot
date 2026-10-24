import {useEffect, useMemo, useState, type FormEvent} from "react";
import {createRoot} from "react-dom/client";
import {
  MantineProvider, Container, Stack, Group, Card, Title, Text, Badge,
  Button, TextInput, Textarea, Select, Switch, Alert, Divider, Tabs,
  PasswordInput, Paper
} from "@mantine/core";
import "@mantine/core/styles.css";
import {parsePageConfig, summary, type Config, type Localized} from "./model";
import {SafeSvgIcon, sanitizeSvg} from "./SafeSvgIcon";
import {STATIC_SVG_PATHS} from "./staticSvgPaths";
import "./admin.css";

/** D1b private UI: all authorization is enforced by the separate Python API.
 * No login token, config, URL or SVG is persisted in localStorage/analytics.
 * The browser never executes imported links or raw SVG and never publishes.
 */
const API="/admin/subpage/api";
type Role="viewer"|"editor"|"owner";
type Session={username:string;role:Role;csrfToken:string;expiresIn:number};
type Snapshot={revision:number;config:Config|null};
type Section="all"|"brandingSettings"|"baseSettings"|"uiConfig"|"baseTranslations"|"platforms"|"svgLibrary";
const SECTIONS:{value:Section;label:string}[]=[
  {value:"all",label:"Вся конфигурация"},{value:"brandingSettings",label:"Брендинг"},
  {value:"baseSettings",label:"Общие настройки"},{value:"uiConfig",label:"Виды карточек"},
  {value:"baseTranslations",label:"Переводы"},{value:"platforms",label:"Устройства и приложения"},
  {value:"svgLibrary",label:"Библиотека SVG (данные)"}
];
const AVAILABLE_PLATFORMS=["ios","android","macos","windows","linux","appleTV","androidTV"];
const APPROVED_SVG_KEYS=Object.keys(STATIC_SVG_PATHS);
/** A missing or quarantined imported key must never look like an approved icon. */
function hasPreviewSvg(key:string|undefined,library:Record<string,string>){
 return Boolean(key&&(Object.hasOwn(STATIC_SVG_PATHS,key)||
   (Object.hasOwn(library,key)&&Boolean(sanitizeSvg(library[key])))));
}
const HEADER={"Content-Type":"application/json"};
function messageOf(error:unknown){return error instanceof Error?error.message:"Неизвестная ошибка";}
function move<T>(items:T[],index:number,delta:number):T[]{
 const copy=[...items],target=index+delta;
 if(target>=0&&target<copy.length){const item=copy.splice(index,1)[0];copy.splice(target,0,item);}
 return copy;
}
function labels(languages:string[],value:string):Localized {
 return Object.fromEntries(languages.map(lang=>[lang,value]));
}
function blockedLinks(config:Config):number {
 let unsafe=0;
 for(const platform of Object.values(config.platforms)){
  for(const app of platform.apps)for(const step of app.blocks)for(const button of step.buttons){
   const link=button.link.trim();
   // Conservative quarantine only; this report never authorizes any actual URL.
   if(link&&!(link.startsWith("https://") || link.includes("{{SUBSCRIPTION_LINK}}"))) unsafe++;
  }
 }
 return unsafe;
}
function deltaSections(base:Config|null,current:Config|null):string[]{
 if(!current)return [];
 if(!base)return ["Вся конфигурация импортирована локально"];
 const sections:Exclude<Section,"all">[]=["brandingSettings","baseSettings","uiConfig","baseTranslations","platforms","svgLibrary"];
 return sections.filter(key=>JSON.stringify(base[key])!==JSON.stringify(current[key]));
}
function safeFilename(name:string){return name.replace(/[^a-z0-9_-]/gi,"-").slice(0,40);}
function exportJson(config:Config,section:Section){
 const contents=section==="all"
  ? config
  : {format:"raccoon-d1b-section-v1",section,data:config[section]};
 const url=URL.createObjectURL(new Blob([JSON.stringify(contents,null,2)+"\n"],{type:"application/json;charset=utf-8"}));
 const a=document.createElement("a");
 a.href=url;a.download="subpage-"+safeFilename(section)+".json";
 document.body.append(a);a.click();a.remove();
 setTimeout(()=>URL.revokeObjectURL(url),0);
}
function unpackSection(raw:string,previous:Config|null):Config {
 const source:unknown=JSON.parse(raw);
 if(source===null||typeof source!=="object"||Array.isArray(source))throw new Error("Нужен JSON-объект");
 const object=source as Record<string,unknown>;
 if(object.format==="raccoon-d1b-section-v1"){
  if(!previous)throw new Error("Сначала загрузите базовую конфигурацию");
  if(Object.keys(object).sort().join(",")!=="data,format,section")throw new Error("Недопустимые поля выборочного импорта");
  const section=SECTIONS.find(x=>x.value===object.section&&x.value!=="all");
  if(!section)throw new Error("Неизвестный раздел");
  const next=structuredClone(previous) as Config;
  // Switch is deliberately explicit: prevents prototype/property injection.
  switch(section.value){
   case "brandingSettings":next.brandingSettings=object.data as Config["brandingSettings"];break;
   case "baseSettings":next.baseSettings=object.data as Config["baseSettings"];break;
   case "uiConfig":next.uiConfig=object.data as Config["uiConfig"];break;
   case "baseTranslations":next.baseTranslations=object.data as Config["baseTranslations"];break;
   case "platforms":next.platforms=object.data as Config["platforms"];break;
   case "svgLibrary":next.svgLibrary=object.data as Config["svgLibrary"];break;
  }
  return parsePageConfig(JSON.stringify(next));
 }
 return parsePageConfig(raw);
}
function App(){
 const [session,setSession]=useState<Session|null>(null);
 const [checking,setChecking]=useState(true);
 const [username,setUsername]=useState("");
 const [password,setPassword]=useState("");
 const [baseline,setBaseline]=useState<Config|null>(null);
 const [draft,setDraft]=useState<Config|null>(null);
 const [revision,setRevision]=useState(0);
 const [dirty,setDirty]=useState(false);
 const [alert,setAlert]=useState("");
 const [success,setSuccess]=useState("");
 const [busy,setBusy]=useState(false);
 const [history,setHistory]=useState<Array<{revision:number;digest:string;actor:string;saved_at:string}>>([]);
 const [language,setLanguage]=useState("ru");
 const [platformKey,setPlatformKey]=useState("ios");
 const [appIndex,setAppIndex]=useState(0);
 const [stepIndex,setStepIndex]=useState(0);
 const [buttonIndex,setButtonIndex]=useState(0);
 const [translationKey,setTranslationKey]=useState("");
 const [newKey,setNewKey]=useState("");
 const [exportSection,setExportSection]=useState<Section>("all");

 async function loadData(){
  const response=await fetch(API+"/draft",{credentials:"same-origin",cache:"no-store"});
  if(!response.ok)throw new Error("Нет доступа к черновику");
  const payload=await response.json() as Snapshot;
  setBaseline(payload.config);setDraft(payload.config?structuredClone(payload.config):null);
  setRevision(payload.revision);setDirty(false);
  const h=await fetch(API+"/history",{credentials:"same-origin",cache:"no-store"});
  if(h.ok){const v=await h.json() as {revisions:typeof history};setHistory(v.revisions);}
 }
 useEffect(()=>{
  let alive=true;
  void (async()=>{
   try {
    const response=await fetch(API+"/session",{credentials:"same-origin",cache:"no-store"});
    if(response.ok&&alive){
     const auth=await response.json() as Session;
     setSession(auth);
     // loadData is also invoked after a successful new login.
     await loadData();
    }
   }catch{if(alive)setAlert("Сервер D1b недоступен: редактор не подключён к runtime");}
   finally{if(alive)setChecking(false);}
  })();
  return()=>{alive=false;};
 },[]);
 const valid=useMemo(()=>{
  if(!draft)return "";
  try{parsePageConfig(JSON.stringify(draft));return "";}
  catch(error){return messageOf(error);}
 },[draft]);
 const changes=useMemo(()=>deltaSections(baseline,draft),[baseline,draft]);
 const riskCount=useMemo(()=>draft?blockedLinks(draft):0,[draft]);
 const canEdit=session?.role==="owner"||session?.role==="editor";
 const isOwner=session?.role==="owner";
 const platform=draft?.platforms[platformKey];
 const app=platform?.apps[appIndex];
 const step=app?.blocks[stepIndex];
 const button=step?.buttons[buttonIndex];
 const translations=Object.keys(draft?.baseTranslations??{});
 const selectedTranslation=translations.includes(translationKey)?translationKey:translations[0];
 const selectedLang=draft?.locales.includes(language)?language:(draft?.locales[0]??"ru");

 function update(modifier:(working:Config)=>void){
  if(!canEdit)return;
  setDraft(previous=>{
   if(!previous)return null;
   const result=structuredClone(previous);
   modifier(result);
   return result;
  });
  setDirty(true);setSuccess("");
 }
 const brand=(field:keyof Config["brandingSettings"],value:string)=>
  update(w=>{w.brandingSettings[field]=value;});
 const setBase=(field:keyof Config["baseSettings"],value:boolean|string)=>
  update(w=>{(w.baseSettings as unknown as Record<string,boolean|string>)[field]=value;});

 async function logIn(event:FormEvent){
  event.preventDefault();setAlert("");setSuccess("");setBusy(true);
  try{
   const response=await fetch(API+"/session",{method:"POST",credentials:"same-origin",
    headers:HEADER,body:JSON.stringify({username,password})});
   if(!response.ok)throw new Error(response.status===429?"Слишком много попыток":"Неверные данные или доступ запрещён");
   const auth=await response.json() as Session;setSession(auth);setPassword("");
   await loadData();
  }catch(error){setAlert(messageOf(error));}
  finally{setBusy(false);}
 }
 async function logOut(){
  setBusy(true);setAlert("");
  try{
   await fetch(API+"/session",{method:"DELETE",credentials:"same-origin",
    headers:{"X-CSRF-Token":session?.csrfToken??""}});
   setSession(null);setDraft(null);setBaseline(null);setHistory([]);setDirty(false);
  }catch(error){setAlert(messageOf(error));}
  finally{setBusy(false);}
 }
 async function importFile(file:File|null){
  if(!file)return;
  setAlert("");setSuccess("");
  if(file.size>1048576){setAlert("Размер конфигурации превышает 1 МиБ");return;}
  try{
   const parsed=unpackSection(await file.text(),draft);
   setDraft(parsed);setDirty(true);setPlatformKey(Object.keys(parsed.platforms)[0]??"ios");
   setAppIndex(0);setStepIndex(0);setButtonIndex(0);
   setSuccess("Импортирован локальный черновик. На сервер ничего ещё не отправлено.");
  }catch{setAlert("Недопустимый JSON или неподдерживаемый формат v1");}
 }
 async function save(){
  if(!draft||!session||!canEdit||valid)return;
  setBusy(true);setAlert("");setSuccess("");
  try{
   const response=await fetch(API+"/draft",{method:"PUT",credentials:"same-origin",
    headers:{...HEADER,"If-Match":'"rev-'+revision+'"',"X-CSRF-Token":session.csrfToken},
    body:JSON.stringify({config:draft})});
   if(!response.ok)throw new Error(response.status===409
    ?"Черновик изменён в другой сессии: сохранение отклонено (409). Экспортируйте свои правки и обновите версию."
    :response.status===403?"Нет прав или неверный CSRF":"Сервер отказал в сохранении");
   const payload=await response.json() as {revision:number};
   setRevision(payload.revision);setBaseline(structuredClone(draft));setDirty(false);
   setSuccess("Зашифрованный черновик сохранён. Это НЕ публикация.");
   const h=await fetch(API+"/history",{credentials:"same-origin",cache:"no-store"});
   if(h.ok)setHistory((await h.json() as {revisions:typeof history}).revisions);
  }catch(error){setAlert(messageOf(error));}
  finally{setBusy(false);}
 }
 async function propose(){
  if(!session||!isOwner||dirty||!revision||valid)return;
  setBusy(true);setAlert("");setSuccess("");
  try{
   const response=await fetch(API+"/proposals",{method:"POST",credentials:"same-origin",
    headers:{"If-Match":'"rev-'+revision+'"',"X-CSRF-Token":session.csrfToken}});
   if(!response.ok)throw new Error(response.status===409
    ?"Версия черновика изменилась":"Предложение не принято");
   const proposal=await response.json() as {proposalId:string};
   setSuccess("Создано предложение для ручной проверки: "+proposal.proposalId+". Публикация заблокирована.");
  }catch(error){setAlert(messageOf(error));}
  finally{setBusy(false);}
 }
 if(checking)return <MantineProvider defaultColorScheme="dark"><div className="admin-shell"><Text>Проверка отдельной админ-сессии…</Text></div></MantineProvider>;
 if(!session)return <MantineProvider defaultColorScheme="dark"><div className="admin-shell">
   <Container size={490}><Card className="admin-login" padding="xl">
    <Badge color="cyan">D1b · только администратор</Badge>
    <Title order={2}>Защищённый редактор</Title>
    <Text c="dimmed" size="sm">Отдельная серверная аутентификация. Telegram и ссылка подписки не дают права входа.</Text>
    {alert&&<Alert color="red" role="alert">{alert}</Alert>}
    <form onSubmit={e=>void logIn(e)}><Stack>
     <TextInput label="Имя администратора" value={username} onChange={e=>setUsername(e.currentTarget.value)} required autoComplete="username"/>
     <PasswordInput label="Пароль" value={password} onChange={e=>setPassword(e.currentTarget.value)} required autoComplete="current-password"/>
     <Button type="submit" loading={busy}>Войти</Button>
    </Stack></form>
    <Text c="dimmed" size="xs">API доступен только после отдельного HTTPS-развёртывания. В основной бот D1b не включён.</Text>
   </Card></Container></div></MantineProvider>;

 return <MantineProvider defaultColorScheme="dark"><div className="admin-shell">
 <Container size="xl" py="xl">
  <header className="admin-header"><Group justify="space-between" align="flex-start">
   <div><Badge color="cyan" variant="light">D1b · draft-only</Badge><Title order={1}>Редактор страницы подписки</Title>
    <Text c="dimmed">Отдельная веб-админка · безопасный импорт и локальный предпросмотр</Text></div>
   <Group><Badge color="teal">{session.role}</Badge><Text size="sm">{session.username}</Text><Button variant="default" onClick={()=>void logOut()} disabled={busy}>Выйти</Button></Group>
  </Group></header>
  <Stack gap="md" mt="lg">
   {alert&&<Alert role="alert" color="red" withCloseButton onClose={()=>setAlert("")}>{alert}</Alert>}
   {success&&<Alert role="status" color="teal" withCloseButton onClose={()=>setSuccess("")}>{success}</Alert>}
   <Alert color="blue">Не подключено к продакшену. Никаких действий публикации, выдачи ключей или запуска deeplink нет. Все URLs/SVG из JSON остаются инертными.</Alert>
   <Group justify="space-between" className="admin-toolbar">
    <Group><Badge color={dirty?"yellow":"teal"}>{dirty?"Локальные изменения":"Синхронизировано"}</Badge>
      <Text size="sm">Версия: {revision}</Text><Text size="sm">Роль: {session.role}</Text></Group>
    <Group>
      <label className="admin-file">Импорт JSON
       <input aria-label="Импортировать конфигурацию редактора" type="file" accept=".json,application/json" onChange={e=>void importFile(e.currentTarget.files?.[0]??null)} disabled={!canEdit||busy}/>
      </label>
      <Select aria-label="Раздел экспорта" size="sm" w={195} data={SECTIONS} value={exportSection} onChange={v=>setExportSection((v??"all") as Section)} disabled={!draft}/>
      <Button variant="light" disabled={!draft} onClick={()=>draft&&exportJson(draft,exportSection)}>Экспорт JSON</Button>
      <Button variant="default" onClick={()=>void loadData().catch(e=>setAlert(messageOf(e)))} disabled={busy}>Обновить с сервера</Button>
      <Button disabled={!draft||!dirty||!canEdit||Boolean(valid)||busy} loading={busy} onClick={()=>void save()}>Сохранить черновик</Button>
    </Group>
   </Group>
   {!draft?<Card padding="xl"><Title order={3}>Черновик пока пуст</Title><Text c="dimmed">Загрузите ваш приватный JSON локально. Он остаётся в браузере до явного нажатия «Сохранить черновик».</Text></Card>:
   <>
    {valid&&<Alert color="red">Не прошла валидация JSON v1: {valid}</Alert>}
    <Group align="stretch" gap="md" className="admin-panels">
     <Card className="admin-editor" padding="lg">
      <Group justify="space-between" mb="sm"><Title order={3}>Конфигурация</Title><Badge>{summary(draft).apps} приложений · {summary(draft).blocks} шагов</Badge></Group>
      <Select label="Язык редактирования" value={selectedLang} data={draft.locales.map(l=>({value:l,label:l.toUpperCase()}))} onChange={v=>{if(v)setLanguage(v);}}/>
      <Tabs defaultValue="brand" mt="md" keepMounted={false}>
       <Tabs.List>
        <Tabs.Tab value="brand">Брендинг</Tabs.Tab><Tabs.Tab value="translations">Переводы</Tabs.Tab>
        <Tabs.Tab value="platforms">Устройства</Tabs.Tab><Tabs.Tab value="steps">Шаги и кнопки</Tabs.Tab>
       </Tabs.List>
       <Tabs.Panel value="brand" pt="lg"><Stack>
        <TextInput label="Название" disabled={!canEdit} value={draft.brandingSettings.title} onChange={e=>brand("title",e.currentTarget.value)}/>
        <TextInput label="Логотип — исходный URL (без выполнения)" disabled={!canEdit} value={draft.brandingSettings.logoUrl} onChange={e=>brand("logoUrl",e.currentTarget.value)}/>
        <TextInput label="Поддержка — исходный URL" disabled={!canEdit} value={draft.brandingSettings.supportUrl} onChange={e=>brand("supportUrl",e.currentTarget.value)}/>
        <TextInput label="Meta title" disabled={!canEdit} value={draft.baseSettings.metaTitle} onChange={e=>setBase("metaTitle",e.currentTarget.value)}/>
        <Textarea label="Meta description" disabled={!canEdit} value={draft.baseSettings.metaDescription} onChange={e=>setBase("metaDescription",e.currentTarget.value)}/>
        <Switch label="Скрывать кнопку получения ссылки" disabled={!canEdit} checked={draft.baseSettings.hideGetLinkButton} onChange={e=>setBase("hideGetLinkButton",e.currentTarget.checked)}/>
        <Switch label="Показывать ключи в интерфейсе (не даёт прав на реальные ключи)" disabled={!canEdit} checked={draft.baseSettings.showConnectionKeys} onChange={e=>setBase("showConnectionKeys",e.currentTarget.checked)}/>
        <Select label="Карточка подписки" disabled={!canEdit} value={draft.uiConfig.subscriptionInfoBlockType}
         data={["expanded","collapsed","cards","hidden"]} onChange={v=>v&&update(w=>{w.uiConfig.subscriptionInfoBlockType=v;})}/>
        <Select label="Инструкции" disabled={!canEdit} value={draft.uiConfig.installationGuidesBlockType}
         data={["cards","timeline","accordion","minimal"]} onChange={v=>v&&update(w=>{w.uiConfig.installationGuidesBlockType=v;})}/>
       </Stack></Tabs.Panel>
       <Tabs.Panel value="translations" pt="lg"><Stack>
        <Select label="Ключ перевода" data={translations} value={selectedTranslation??null}
          onChange={v=>setTranslationKey(v??"")}/>
        {selectedTranslation&&<Textarea label={"Текст ("+selectedLang+")"} disabled={!canEdit}
         value={draft.baseTranslations[selectedTranslation]?.[selectedLang]??""} autosize minRows={3}
         onChange={e=>{const value=e.currentTarget.value;update(w=>{w.baseTranslations[selectedTranslation][selectedLang]=value;});}}/>}
        <Group><TextInput label="Добавить ключ" placeholder="newTranslation" value={newKey} onChange={e=>setNewKey(e.currentTarget.value)} disabled={!canEdit}/>
         <Button disabled={!canEdit||!newKey.match(/^[a-zA-Z][a-zA-Z0-9_]{1,63}$/)||translations.includes(newKey)} mt="lg" onClick={()=>{
          update(w=>{w.baseTranslations[newKey]=labels(w.locales,"");});
          setTranslationKey(newKey);setNewKey("");
         }}>Добавить</Button></Group>
        {selectedTranslation&&<Button color="red" variant="subtle" disabled={!canEdit} onClick={()=>{
          update(w=>{delete w.baseTranslations[selectedTranslation];});setTranslationKey("");
        }}>Удалить выбранный ключ</Button>}
       </Stack></Tabs.Panel>
       <Tabs.Panel value="platforms" pt="lg"><Stack>
        <Select label="Платформа" value={platformKey} data={Object.keys(draft.platforms)} onChange={v=>{if(v){setPlatformKey(v);setAppIndex(0);setStepIndex(0);}}}/>
        <Group>
         <Select label="Добавить платформу" placeholder="Выберите отсутствующую" value={null}
          disabled={!canEdit} data={AVAILABLE_PLATFORMS.filter(p=>!draft.platforms[p])}
          onChange={v=>{if(v){update(w=>{w.platforms[v]={apps:[],displayName:labels(w.locales,v),svgIconKey:""};});setPlatformKey(v);setAppIndex(0);}}}/>
         <Button color="red" variant="subtle" disabled={!canEdit||!platform} onClick={()=>{
          update(w=>{delete w.platforms[platformKey];});
          setPlatformKey(AVAILABLE_PLATFORMS.find(k=>k!==platformKey&&Boolean(draft.platforms[k]))??"ios");
         }}>Удалить платформу</Button>
        </Group>
        {platform&&<>
          <TextInput label={"Название платформы ("+selectedLang+")"} value={platform.displayName[selectedLang]??""} disabled={!canEdit}
           onChange={e=>{const value=e.currentTarget.value;update(w=>{w.platforms[platformKey].displayName[selectedLang]=value;});}}/>
          <TextInput label="SVG icon key" value={platform.svgIconKey} disabled={!canEdit}
           onChange={e=>{const value=e.currentTarget.value;update(w=>{w.platforms[platformKey].svgIconKey=value;});}}/>
          <Select label="VPN-приложение" value={platform.apps.length?String(Math.min(appIndex,platform.apps.length-1)):null}
           data={platform.apps.map((a,i)=>({label:a.name||"Новый клиент",value:String(i)}))}
           onChange={v=>{setAppIndex(Number(v??0));setStepIndex(0);setButtonIndex(0);}}/>
          <Group><Button disabled={!canEdit} onClick={()=>{update(w=>{w.platforms[platformKey].apps.push({name:"Новый клиент",featured:false,svgIconKey:"",blocks:[]});});setAppIndex(platform.apps.length);}}>
            Добавить приложение</Button>
           <Button variant="light" disabled={!canEdit||!app||appIndex<=0} onClick={()=>{update(w=>{w.platforms[platformKey].apps=move(w.platforms[platformKey].apps,appIndex,-1);});setAppIndex(appIndex-1);}}>Выше</Button>
           <Button variant="light" disabled={!canEdit||!app||appIndex>=platform.apps.length-1} onClick={()=>{update(w=>{w.platforms[platformKey].apps=move(w.platforms[platformKey].apps,appIndex,1);});setAppIndex(appIndex+1);}}>Ниже</Button>
           <Button color="red" variant="light" disabled={!canEdit||!app} onClick={()=>{update(w=>{w.platforms[platformKey].apps.splice(appIndex,1);});setAppIndex(0);}}>Удалить</Button>
          </Group>
          {app&&<>
           <TextInput label="Название приложения" disabled={!canEdit} value={app.name}
            onChange={e=>{const value=e.currentTarget.value;update(w=>{w.platforms[platformKey].apps[appIndex].name=value;});}}/>
           <TextInput label="Ключ SVG" disabled={!canEdit} value={app.svgIconKey}
            onChange={e=>{const value=e.currentTarget.value;update(w=>{w.platforms[platformKey].apps[appIndex].svgIconKey=value;});}}/>
           <Switch label="Выделенный клиент" checked={app.featured} disabled={!canEdit}
            onChange={e=>{const val=e.currentTarget.checked;update(w=>{w.platforms[platformKey].apps[appIndex].featured=val;});}}/>
          </>}
         </>}
       </Stack></Tabs.Panel>
       <Tabs.Panel value="steps" pt="lg"><Stack>
        <Text size="sm" c="dimmed">Платформа: {platformKey}, приложение: {app?.name??"не выбрано"}. Тексты редактируются без запуска внешних ссылок.</Text>
        {app&&<>
         <Select label="Шаг подключения" value={step?String(stepIndex):null} data={app.blocks.map((b,i)=>({value:String(i),label:(b.title[selectedLang]||"Шаг")+" #"+(i+1)}))}
           onChange={v=>{setStepIndex(Number(v??0));setButtonIndex(0);}}/>
         <Group>
          <Button disabled={!canEdit} onClick={()=>{update(w=>{w.platforms[platformKey].apps[appIndex].blocks.push({title:labels(w.locales,"Новый шаг"),description:labels(w.locales,""),svgIconKey:"",svgIconColor:"",buttons:[]});});setStepIndex(app.blocks.length);}}>Добавить шаг</Button>
          <Button variant="light" disabled={!canEdit||!step||stepIndex<=0} onClick={()=>{update(w=>{const a=w.platforms[platformKey].apps[appIndex];a.blocks=move(a.blocks,stepIndex,-1);});setStepIndex(stepIndex-1);}}>Выше</Button>
          <Button variant="light" disabled={!canEdit||!step||stepIndex>=app.blocks.length-1} onClick={()=>{update(w=>{const a=w.platforms[platformKey].apps[appIndex];a.blocks=move(a.blocks,stepIndex,1);});setStepIndex(stepIndex+1);}}>Ниже</Button>
          <Button color="red" variant="light" disabled={!canEdit||!step} onClick={()=>{update(w=>{w.platforms[platformKey].apps[appIndex].blocks.splice(stepIndex,1);});setStepIndex(0);}}>Удалить шаг</Button>
         </Group>
         {step&&<>
          <TextInput label={"Заголовок шага ("+selectedLang+")"} disabled={!canEdit} value={step.title[selectedLang]??""}
           onChange={e=>{const val=e.currentTarget.value;update(w=>{w.platforms[platformKey].apps[appIndex].blocks[stepIndex].title[selectedLang]=val;});}}/>
          <Textarea label={"Описание ("+selectedLang+")"} disabled={!canEdit} minRows={3} autosize value={step.description[selectedLang]??""}
           onChange={e=>{const val=e.currentTarget.value;update(w=>{w.platforms[platformKey].apps[appIndex].blocks[stepIndex].description[selectedLang]=val;});}}/>
          <TextInput label="SVG icon key шага" disabled={!canEdit} value={step.svgIconKey}
           onChange={e=>{const val=e.currentTarget.value;update(w=>{w.platforms[platformKey].apps[appIndex].blocks[stepIndex].svgIconKey=val;});}}/>
          <TextInput label="SVG icon color" disabled={!canEdit} value={step.svgIconColor}
           onChange={e=>{const val=e.currentTarget.value;update(w=>{w.platforms[platformKey].apps[appIndex].blocks[stepIndex].svgIconColor=val;});}}/>
          <Divider label="Кнопки шага" labelPosition="center"/>
          <Select label="Кнопка" value={button?String(buttonIndex):null} data={step.buttons.map((b,i)=>({value:String(i),label:(b.text[selectedLang]||"Кнопка")+" #"+(i+1)}))}
           onChange={v=>setButtonIndex(Number(v??0))}/>
          <Group>
           <Button disabled={!canEdit} onClick={()=>{update(w=>{w.platforms[platformKey].apps[appIndex].blocks[stepIndex].buttons.push({type:"external",link:"",text:labels(w.locales,"Действие"),svgIconKey:""});});setButtonIndex(step.buttons.length);}}>Добавить кнопку</Button>
           <Button color="red" variant="light" disabled={!canEdit||!button} onClick={()=>{update(w=>{w.platforms[platformKey].apps[appIndex].blocks[stepIndex].buttons.splice(buttonIndex,1);});setButtonIndex(0);}}>Удалить кнопку</Button>
          </Group>
          {button&&<>
           <TextInput label={"Текст кнопки ("+selectedLang+")"} disabled={!canEdit} value={button.text[selectedLang]??""}
            onChange={e=>{const val=e.currentTarget.value;update(w=>{w.platforms[platformKey].apps[appIndex].blocks[stepIndex].buttons[buttonIndex].text[selectedLang]=val;});}}/>
           <Select label="Тип кнопки" disabled={!canEdit} value={button.type} data={["external","subscriptionLink","copyButton"]}
            onChange={v=>v&&update(w=>{w.platforms[platformKey].apps[appIndex].blocks[stepIndex].buttons[buttonIndex].type=v as "external"|"subscriptionLink"|"copyButton";})}/>
           <Textarea label="Ссылка/шаблон (НЕ исполняется)" disabled={!canEdit} value={button.link} autosize
            onChange={e=>{const val=e.currentTarget.value;update(w=>{w.platforms[platformKey].apps[appIndex].blocks[stepIndex].buttons[buttonIndex].link=val;});}}/>
          </>}
         </>}
        </>}
       </Stack></Tabs.Panel>
      </Tabs>
     </Card>
     <Card className="admin-preview" padding="lg">
      <Group justify="space-between"><Title order={3}>Безопасный предпросмотр</Title><Badge color="cyan">Без реальных действий</Badge></Group>
      <Title order={2} mt="lg">{draft.brandingSettings.title||"Страница подписки"}</Title>
      <Text c="dimmed" mt="xs">{draft.baseSettings.metaDescription||"Предпросмотр конфигурации"}</Text>
      <Paper p="md" mt="lg" className="admin-demo-card">
       <Badge color="yellow">ДЕМО</Badge><Title order={4} mt="sm">Статус: нет данных</Title>
       <Text size="sm" c="dimmed">Ссылка на подписку и реальные ключи здесь никогда не появляются.</Text>
       <Text mt="sm" size="sm">Карточка: {draft.uiConfig.subscriptionInfoBlockType}</Text>
       <Text size="sm">Инструкции: {draft.uiConfig.installationGuidesBlockType}</Text>
      </Paper>
      <Text fw={700} mt="lg">Выбор устройства</Text>
      <Group mt="xs" gap="xs" className="admin-platforms" data-testid="admin-platforms">{Object.entries(draft.platforms).map(([key,p])=>
       <Button key={key} size="xs" variant={key===platformKey?"filled":"light"}
        leftSection={<SafeSvgIcon iconKey={p.svgIconKey} library={draft.svgLibrary}
          preferStatic testId="admin-platform-svg" className="admin-svg-icon"
          fallback={<span className="admin-svg-missing" aria-hidden="true">◇</span>}/>}
        onClick={()=>{setPlatformKey(key);setAppIndex(0);setStepIndex(0);}}>{p.displayName[selectedLang]||key}</Button>)}</Group>
      {platform&&<><Text fw={700} mt="lg">Клиенты</Text><Stack gap="xs" mt="xs" data-testid="admin-preview-clients">
       {platform.apps.length===0?<Text c="dimmed">Для платформы нет приложений.</Text>:platform.apps.map((a,i)=>
        <Paper key={i} p="sm" className="admin-demo-card">
         <Group gap="sm" align="flex-start" wrap="nowrap">
          <SafeSvgIcon iconKey={a.svgIconKey} library={draft.svgLibrary} preferStatic
           testId="admin-client-svg" className="admin-svg-client"
           fallback={<span className="admin-svg-missing admin-svg-client" aria-hidden="true">◇</span>}/>
          <div className="admin-preview-copy">
           <Group gap="xs"><Text fw={600}>{a.name}</Text>{a.featured&&<Badge color="teal">Выделен</Badge>}
            {!hasPreviewSvg(a.svgIconKey,draft.svgLibrary)&&<Badge color="yellow">Нет проверенной SVG</Badge>}</Group>
           {a.blocks.length===0?<Text size="xs" c="dimmed">Шаги ещё не указаны.</Text>:
            <Stack gap={6} mt="xs">{a.blocks.map((b,k)=>
             <Group key={k} className="admin-preview-step" gap="xs" align="flex-start" wrap="nowrap">
              <SafeSvgIcon iconKey={b.svgIconKey} library={draft.svgLibrary} preferStatic
               testId="admin-step-svg" className="admin-svg-icon"
               fallback={<span className="admin-svg-missing" aria-hidden="true">◇</span>}/>
              <div className="admin-preview-copy">
               <Text size="xs">{k+1}. {b.title[selectedLang]??""}</Text>
               <Text size="xs" c="dimmed">{b.description[selectedLang]??""}</Text>
               {b.buttons.map((button,index)=>
                <span key={index} className="admin-preview-action" aria-disabled="true"
                  data-testid="admin-disabled-action">
                 <SafeSvgIcon iconKey={button.svgIconKey} library={draft.svgLibrary} preferStatic
                  testId="admin-action-svg" className="admin-svg-icon"
                  fallback={<span className="admin-svg-missing" aria-hidden="true">◇</span>}/>
                 {button.text[selectedLang]??"Действие"} · заблокировано
                </span>)}
              </div>
             </Group>)}</Stack>}
          </div>
         </Group>
        </Paper>)}
      </Stack></>}
      <details className="admin-svg-gallery" data-testid="admin-svg-gallery">
       <summary>Проверенная SVG-библиотека · {APPROVED_SVG_KEYS.length} локальных иконок</summary>
       <Text size="xs" c="dimmed" mt="xs">Самостоятельные локальные файлы; ключи в конфигурации должны совпадать. Сырые SVG не вставляются в HTML.</Text>
       <div className="admin-svg-grid" data-testid="admin-svg-grid">
        {APPROVED_SVG_KEYS.map(key=><div key={key} className="admin-svg-cell">
         <SafeSvgIcon iconKey={key} preferStatic testId="admin-library-svg"
          className="admin-svg-gallery-icon" fallback={<span aria-hidden="true">◇</span>}/>
         <Text size="xs" title={key}>{key}</Text>
        </div>)}
       </div>
      </details>
      <Divider my="lg"/>
      <Text fw={700}>Проверка перед публикацией</Text>
      <Text size="sm" c="dimmed">Изменённые разделы: {changes.join(", ")||"нет"}</Text>
      <Text size="sm" c={riskCount?"red":"dimmed"}>Подозрительных URL/схем в исходных текстах: {riskCount}. Они сохраняются без выполнения и требуют отдельной ручной проверки.</Text>
      <Text size="sm">SVG-ключей в импортированном JSON: {Object.keys(draft.svgLibrary).length}. Локально утверждённых файлов: {APPROVED_SVG_KEYS.length}. Изображения загружаются с этого же origin или проходят SVG sanitizer и показываются только как passive img.</Text>
      <Group mt="lg"><Button variant="light" disabled={!isOwner||!revision||dirty||busy||Boolean(valid)}
       onClick={()=>void propose()}>Предложить к проверке</Button>
       <Button disabled>Опубликовать (заблокировано)</Button></Group>
     </Card>
    </Group>
    <Card padding="lg"><Group justify="space-between"><Title order={3}>Журнал изменений</Title><Badge>Без приватного содержимого</Badge></Group>
      {history.length===0?<Text c="dimmed" mt="sm">Пока нет сохранённых ревизий.</Text>:
       <Stack gap={6} mt="sm">{history.map(item=><Group key={item.revision} justify="space-between">
        <Text size="sm">Версия {item.revision} · {item.actor} · {item.saved_at}</Text>
        <Text c="dimmed" size="xs">SHA-256: {item.digest.slice(0,12)}…</Text></Group>)}</Stack>}
    </Card>
   </>}
  </Stack>
 </Container></div></MantineProvider>;
}

createRoot(document.getElementById("admin-root")!).render(<App/>);
