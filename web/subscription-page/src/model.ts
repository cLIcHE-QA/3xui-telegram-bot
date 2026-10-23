export type Localized = Record<string,string>;
export type Action = {link:string;type:"external"|"subscriptionLink"|"copyButton";text:Localized;svgIconKey:string};
export type Step = {title:Localized;description:Localized;buttons:Action[];svgIconKey:string;svgIconColor:string};
export type Client = {name:string;featured:boolean;svgIconKey:string;blocks:Step[]};
export type Platform = {apps:Client[];displayName:Localized;svgIconKey:string};
export type Config = {version:"1";locales:string[];platforms:Record<string,Platform>;uiConfig:{subscriptionInfoBlockType:string;installationGuidesBlockType:string};svgLibrary:Record<string,string>;baseSettings:{metaTitle:string;metaDescription:string;hideGetLinkButton:boolean;showConnectionKeys:boolean};baseTranslations:Record<string,Localized>;brandingSettings:{title:string;logoUrl:string;supportUrl:string}};
const fields=["baseSettings","baseTranslations","brandingSettings","locales","platforms","svgLibrary","uiConfig","version"];
const languages=["en","ru","zh","fa","fr"], platforms=["ios","linux","macos","android","appleTV","windows","androidTV"];
function check(test:unknown,message:string):asserts test {if(!test)throw new Error(message);}
function object(v:unknown):v is Record<string,unknown>{return v!==null&&typeof v==="object"&&!Array.isArray(v);}
function translated(v:unknown,locales:string[]):void{check(object(v),"Invalid localized field");check(locales.every(l=>typeof v[l]==="string"),"Missing translation");}
export function parsePageConfig(raw:string):Config {
 check(new TextEncoder().encode(raw).length<=1048576,"JSON exceeds 1 MiB");
 let d:unknown;try{d=JSON.parse(raw)}catch{throw new Error("Malformed JSON")}
 const stack:[[unknown,number]]|Array<[unknown,number]>=[[d,0]];
 while(stack.length){const [v,depth]=stack.pop()!;check(depth<=32,"Excessive JSON depth");if(object(v)){for(const [k,x] of Object.entries(v)){check(!["__proto__","constructor","prototype"].includes(k),"Unsafe key");stack.push([x,depth+1]);}}else if(Array.isArray(v)){for(const x of v)stack.push([x,depth+1]);}}
 check(object(d)&&JSON.stringify(Object.keys(d).sort())===JSON.stringify(fields),"Unsupported configuration fields");
 check(d.version==="1","Unsupported version");
 check(Array.isArray(d.locales)&&d.locales.length>0&&d.locales.every(v=>typeof v==="string"&&languages.includes(v))&&new Set(d.locales).size===d.locales.length,"Invalid locales");
 const loc=d.locales as string[];
 check(object(d.uiConfig)&&["expanded","collapsed","cards","hidden"].includes(String(d.uiConfig.subscriptionInfoBlockType))&&["cards","timeline","accordion","minimal"].includes(String(d.uiConfig.installationGuidesBlockType)),"Invalid layout");
 check(object(d.baseSettings)&&typeof d.baseSettings.hideGetLinkButton==="boolean"&&typeof d.baseSettings.showConnectionKeys==="boolean"&&typeof d.baseSettings.metaTitle==="string"&&typeof d.baseSettings.metaDescription==="string","Invalid base settings");
 check(object(d.brandingSettings)&&["title","logoUrl","supportUrl"].every(k=>typeof (d.brandingSettings as Record<string,unknown>)[k]==="string"),"Invalid brand");
 check(object(d.baseTranslations),"Invalid translations");for(const v of Object.values(d.baseTranslations))translated(v,loc);
 check(object(d.svgLibrary)&&Object.values(d.svgLibrary).every(x=>typeof x==="string"),"Invalid icons");
 check(object(d.platforms),"Invalid platforms");
 for(const [name,p] of Object.entries(d.platforms)){
  check(platforms.includes(name)&&object(p)&&Array.isArray(p.apps)&&typeof p.svgIconKey==="string","Invalid platform");
  translated(p.displayName,loc);
  for(const app of p.apps){check(object(app)&&typeof app.name==="string"&&typeof app.featured==="boolean"&&typeof app.svgIconKey==="string"&&Array.isArray(app.blocks),"Invalid app");
   for(const step of app.blocks){check(object(step)&&typeof step.svgIconKey==="string"&&typeof step.svgIconColor==="string"&&Array.isArray(step.buttons),"Invalid step");translated(step.title,loc);translated(step.description,loc);
    for(const bt of step.buttons){check(object(bt)&&typeof bt.link==="string"&&typeof bt.svgIconKey==="string"&&["external","subscriptionLink","copyButton"].includes(String(bt.type)),"Invalid button");translated(bt.text,loc);}
   }
  }
 }
 return d as Config;
}
export const translate=(v:Localized|undefined,l:string)=>v?.[l]??v?.en??"";
export function summary(d:Config){const apps=Object.values(d.platforms).flatMap(p=>p.apps),blocks=apps.flatMap(a=>a.blocks),buttons=blocks.flatMap(s=>s.buttons);return {languages:d.locales.length,platforms:Object.keys(d.platforms).length,apps:apps.length,uniqueClients:new Set(apps.map(a=>a.name)).size,blocks:blocks.length,buttons:buttons.length,icons:Object.keys(d.svgLibrary).length};}
