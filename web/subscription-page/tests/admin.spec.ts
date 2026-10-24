import {expect,test} from "@playwright/test";

/** All responses are synthetic. No credential, private export or actual API host. */
const languages=["en","ru","zh","fa","fr"];
const localized=(s:string)=>Object.fromEntries(languages.map(l=>[l,s+" "+l]));
const fixture={
 locales:languages,version:"1",
 uiConfig:{subscriptionInfoBlockType:"expanded",installationGuidesBlockType:"cards"},
 platforms:{ios:{displayName:localized("iOS"),svgIconKey:"AppleIcon",apps:[{
  name:"Synthetic",featured:true,svgIconKey:"Demo",blocks:[{
   title:localized("Install"),description:localized("Synthetic text"),
   svgIconKey:"Plus",svgIconColor:"#18a5f9",
   buttons:[{type:"external",link:"https://example.invalid/demo",
     svgIconKey:"ExternalLink",text:localized("Open")}],
  }],
 }]}},
 svgLibrary:{Demo:'<svg xmlns="http://www.w3.org/2000/svg"/>'},
 baseSettings:{metaTitle:"Demo",metaDescription:"Preview only",hideGetLinkButton:false,showConnectionKeys:false},
 baseTranslations:{getLink:localized("Get")},
 brandingSettings:{title:"Raccoon sample",logoUrl:"",supportUrl:""},
};

test("отдельная D1b страница закрыта без admin session и не делает внешних запросов",async({page})=>{
 const outbound:string[]=[];
 page.on("request",request=>{
  if(new URL(request.url()).origin!=="http://127.0.0.1:4173")outbound.push(request.url());
 });
 await page.route("**/admin/subpage/api/**",async route=>{
  await route.fulfill({status:401,contentType:"application/json",body:'{"error":"Unauthorized"}'});
 });
 await page.goto("/admin.html");
 await expect(page.getByRole("heading",{name:"Защищённый редактор"})).toBeVisible();
 await expect(page.getByLabel("Имя администратора")).toBeVisible();
 await expect(page.getByLabel("Код подтверждения (MFA)")).toBeVisible();
 await expect(page.getByText("Сохранить черновик")).toHaveCount(0);
 await expect(page.getByText("Опубликовать (заблокировано)")).toHaveCount(0);
 expect(outbound).toEqual([]);
});

test("D1b админ редактор: локальный импорт, валидация, сохранение с CSRF/If-Match и запрет publish",async({page})=>{
 let authenticated=false;
 const requests:Array<{method:string,path:string,headers:Record<string,string>,body:string}>=[];
 await page.route("**/admin/subpage/api/**",async route=>{
  const request=route.request();
  const url=new URL(request.url());
  const method=request.method(),path=url.pathname;
  requests.push({method,path,headers:request.headers(),body:request.postData()??""});
  const respond=async(status:number,body:object,headers:Record<string,string>={})=>
   route.fulfill({status,contentType:"application/json",headers,body:JSON.stringify(body)});
  if(path.endsWith("/session")&&method==="GET")return respond(authenticated?200:401,
    authenticated?{username:"editor1",role:"editor",csrfToken:"synthetic-csrf",expiresIn:120}:{});
  if(path.endsWith("/session")&&method==="POST"){
   authenticated=true;return respond(200,{username:"editor1",role:"editor",csrfToken:"synthetic-csrf",expiresIn:120});
  }
  if(path.endsWith("/draft")&&method==="GET")return respond(200,{revision:0,config:null},{ETag:'"rev-0"'});
  if(path.endsWith("/history")&&method==="GET")return respond(200,{revisions:[]});
  if(path.endsWith("/draft")&&method==="PUT")return respond(200,{revision:1,state:"draft"});
  return respond(403,{error:"Not authorized"});
 });
 await page.goto("/admin.html");
 await expect(page.getByRole("heading",{name:"Защищённый редактор"})).toBeVisible();
 await page.getByLabel("Имя администратора").fill("editor1");
 await page.getByLabel("Пароль").fill("synthetic-password-only");
 await page.getByLabel("Код подтверждения (MFA)").fill("123456");
 await page.getByRole("button",{name:"Войти"}).click();
 await expect(page.getByRole("heading",{name:"Редактор страницы подписки"})).toBeVisible();
 await expect(page.getByText("Черновик пока пуст")).toBeVisible();
 await page.getByLabel("Импортировать конфигурацию редактора").setInputFiles({
  name:"synthetic.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(fixture)),
 });
 await expect(page.getByText("Импортирован локальный черновик")).toBeVisible();
 const sentAfterImport=requests.filter(r=>r.method==="PUT");
 expect(sentAfterImport).toHaveLength(0);
 await expect(page.getByRole("button",{name:"Сохранить черновик"})).toBeEnabled();
 await page.getByRole("button",{name:"Сохранить черновик"}).click();
 await expect(page.getByText("Зашифрованный черновик сохранён")).toBeVisible();
 const saves=requests.filter(r=>r.method==="PUT");
 expect(saves).toHaveLength(1);
 expect(saves[0].headers["x-csrf-token"]).toBe("synthetic-csrf");
 expect(saves[0].headers["if-match"]).toBe('"rev-0"');
 expect(JSON.parse(saves[0].body).config.brandingSettings.title).toBe("Raccoon sample");
 await expect(page.getByRole("button",{name:"Опубликовать (заблокировано)"})).toBeDisabled();
 await expect(page.getByRole("button",{name:"Завершить все сеансы"})).toBeVisible();
 await expect(page.getByRole("button",{name:"Предложить к проверке"})).toBeDisabled();
});

test("D1b выборочный экспорт не выдаёт внешние URL через network и контроль viewer",async({page})=>{
 const remote:string[]=[];
 page.on("request",r=>{if(new URL(r.url()).origin!=="http://127.0.0.1:4173")remote.push(r.url());});
 await page.route("**/admin/subpage/api/**",async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;
  const body=path.endsWith("/session")?{username:"viewer1",role:"viewer",csrfToken:"only-test",expiresIn:120}
     :path.endsWith("/draft")?{revision:2,config:fixture}:{revisions:[]};
  await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(body)});
 });
 await page.goto("/admin.html");
 await expect(page.getByRole("heading",{name:"Редактор страницы подписки"})).toBeVisible();
 await expect(page.getByRole("button",{name:"Сохранить черновик"})).toBeDisabled();
 await expect(page.getByRole("button",{name:"Предложить к проверке"})).toBeDisabled();
 await expect(page.getByRole("button",{name:"Опубликовать (заблокировано)"})).toBeDisabled();
 expect(remote).toEqual([]);
});

test("D1b preview matches approved self-hosted SVG catalog without executing imported SVG",async({page})=>{
 await page.setViewportSize({width:1280,height:900});
 const network:string[]=[];
 page.on("request",r=>{if(new URL(r.url()).origin!=="http://127.0.0.1:4173")network.push(r.url());});
 const config=structuredClone(fixture);
 config.platforms.ios.apps=[
  {...structuredClone(fixture.platforms.ios.apps[0]),name:"Синтетический Happ",svgIconKey:"Happ"},
  {...structuredClone(fixture.platforms.ios.apps[0]),name:"Синтетический RabbitHole",svgIconKey:"RabbitHole"},
  {...structuredClone(fixture.platforms.ios.apps[0]),name:"Синтетический INCY",svgIconKey:"INCY"},
  {...structuredClone(fixture.platforms.ios.apps[0]),name:"Без SVG",svgIconKey:"unsafeIcon"},
 ];
 config.svgLibrary={
  ...fixture.svgLibrary,
  Happ:'<svg xmlns="http://www.w3.org/2000/svg"><circle cx="5" cy="5" r="4" fill="#f55"/></svg>',
  unsafeIcon:'<svg xmlns="http://www.w3.org/2000/svg"><script>alert("unsafe")</script></svg>',
 };
 await page.route("**/admin/subpage/api/**",async route=>{
  const path=new URL(route.request().url()).pathname;
  const body=path.endsWith("/session")?
   {username:"viewer1",role:"viewer",csrfToken:"only-test",expiresIn:120}:
   path.endsWith("/draft")?{revision:1,config}:{revisions:[]};
  await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(body)});
 });
 await page.goto("/admin.html");
 await expect(page.getByRole("heading",{name:"Редактор страницы подписки"})).toBeVisible();
 await expect(page.getByTestId("admin-platform-svg").first()).toHaveAttribute("src","/client-icons/library/AppleIcon.svg");
 const icons=page.getByTestId("admin-client-svg");
 await expect(icons).toHaveCount(3);
 await expect(icons.nth(0)).toHaveAttribute("src","/client-icons/library/Happ.svg");
 await expect(icons.nth(1)).toHaveAttribute("src","/client-icons/library/RabbitHole.svg");
 await expect(icons.nth(2)).toHaveAttribute("src","/client-icons/incy.svg");
 await expect(page.getByText("Нет проверенной SVG")).toBeVisible();
 await expect(page.getByTestId("admin-step-svg")).toHaveCount(4);
 const buttons=page.getByTestId("admin-disabled-action");
 await expect(buttons).toHaveCount(4);
 await expect(buttons.first()).toHaveAttribute("aria-disabled","true");
 await expect(buttons.first().getByTestId("admin-action-svg")).toHaveAttribute("src","/client-icons/library/ExternalLink.svg");
 await page.getByTestId("admin-svg-gallery").locator("summary").click();
 await expect(page.getByTestId("admin-library-svg")).toHaveCount(40);
 await expect(page.getByTestId("admin-library-svg").last()).toHaveAttribute("src","/client-icons/incy.svg");
 await expect.poll(async()=>page.getByTestId("admin-library-svg").evaluateAll(
    nodes=>nodes.filter(node=>node instanceof HTMLImageElement && node.complete && node.naturalWidth>0).length
 )).toBe(40);
 const backplate=await page.getByTestId("admin-library-svg").first().evaluate(node=>getComputedStyle(node).backgroundImage);
 expect(backplate).toContain("linear-gradient");
 await page.screenshot({path:"test-results/d1b-svg-approved-library-desktop.png",fullPage:true});
 expect(network).toEqual([]);
});

test("D1b SVG gallery remains readable at mobile width and 200% text",async({page})=>{
 const config=structuredClone(fixture);
 config.platforms.ios.apps[0].svgIconKey="Shadowrocket";
 await page.route("**/admin/subpage/api/**",async route=>{
  const path=new URL(route.request().url()).pathname;
  const response=path.endsWith("/session")?
    {username:"viewer1",role:"viewer",csrfToken:"test",expiresIn:120}:
    path.endsWith("/draft")?{revision:1,config}:{revisions:[]};
  await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(response)});
 });
 await page.setViewportSize({width:320,height:720});
 await page.goto("/admin.html");
 await expect(page.getByTestId("admin-client-svg")).toHaveAttribute("src","/client-icons/library/Shadowrocket.svg");
 await page.getByTestId("admin-svg-gallery").locator("summary").click();
 await page.addStyleTag({content:":root{font-size:200% !important}"});
 await expect(page.getByTestId("admin-svg-gallery")).toBeVisible();
 const title=page.getByRole("heading",{name:"Безопасный предпросмотр"});
 await expect(title).toBeVisible();
 const unclipped=await title.evaluate(node=>node.scrollWidth<=node.clientWidth+1);
 expect(unclipped,"200%-text mobile preview heading must not be clipped").toBe(true);
 const badge=page.locator(".admin-preview-status");
 await expect(badge).toBeVisible();
 const badgeFits=await badge.evaluate(node=>node.scrollWidth<=node.clientWidth+1);
 expect(badgeFits,"200%-text D1b status badge must not be clipped").toBe(true);
 const switchBody=page.locator(".admin-editor .mantine-Switch-body").first();
 await expect(switchBody).toHaveCSS("flex-direction","column");
 const switchLabel=page.locator(".admin-editor .mantine-Switch-label").first();
 const switchUnclipped=await switchLabel.evaluate(node=>node.scrollWidth<=node.clientWidth+1);
 expect(switchUnclipped,"200%-text admin toggle description must not be clipped").toBe(true);
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);
 expect(overflow).toBe(false);
 await page.screenshot({path:"test-results/d1b-svg-approved-library-mobile-200-percent.png",fullPage:true});
});
