import test from "node:test";
import assert from "node:assert/strict";
import {parsePageConfig,summary,translate,instructionInventory} from "./model.ts";
const langs=["en","ru","zh","fa","fr"];const loc=(s:string)=>Object.fromEntries(langs.map(x=>[x,s+x]));
const original={locales:langs,version:"1",uiConfig:{subscriptionInfoBlockType:"expanded",installationGuidesBlockType:"cards"},platforms:{ios:{displayName:loc("iOS"),svgIconKey:"Apple",apps:[{name:"Synthetic",featured:true,svgIconKey:"Client",blocks:[{title:loc("Install"),description:loc("Description"),svgIconKey:"Plus",svgIconColor:"teal",buttons:[{link:"client://add/{{SUBSCRIPTION_LINK}}",text:loc("Import"),type:"subscriptionLink",svgIconKey:"ExternalLink"}]}]}]}},svgLibrary:{Client:"<svg/>"},baseSettings:{metaTitle:"Test",metaDescription:"Test",hideGetLinkButton:false,showConnectionKeys:false},baseTranslations:{getLink:loc("Get")},brandingSettings:{title:"Test",logoUrl:"",supportUrl:""}};
test("lossless v1 import, language order and inert link templates",()=>{const doc=parsePageConfig(JSON.stringify(original));assert.deepEqual(doc,original);assert.deepEqual(JSON.parse(JSON.stringify(doc)),original);assert.equal(translate(doc.baseTranslations.getLink,"fa"),"Getfa");assert.deepEqual(summary(doc),{languages:5,platforms:1,apps:1,uniqueClients:1,blocks:1,buttons:1,icons:1});});
test("negative validation",()=>{assert.throws(()=>parsePageConfig("invalid"));assert.throws(()=>parsePageConfig(JSON.stringify({...original,version:"2"})));assert.throws(()=>parsePageConfig(JSON.stringify({...original,baseSettings:{...original.baseSettings,showConnectionKeys:"yes"}})));assert.throws(()=>parsePageConfig(JSON.stringify(original).replace('"version":"1"','"__proto__":{},"version":"1"')));});


test("92 инструкций и 75 кнопок: синтетический 5/7/24 паритет без пользовательских данных",()=>{
 const platformKeys=["ios","linux","macos","android","appleTV","windows","androidTV"];
 const platformCounts=[4,3,4,4,3,4,2];
 let appIndex=0,stepIndex=0;
 const config={
  ...original,
  platforms:Object.fromEntries(platformKeys.map((key,i)=>[key,{
   displayName:loc(key),svgIconKey:"TestPlatform",
   apps:Array.from({length:platformCounts[i]},()=>{
    const slot=appIndex++;
    return {name:"Synthetic client "+(slot%10),featured:slot===0,svgIconKey:"TestClient",
     blocks:Array.from({length:slot<4?3:4},()=>{
      const index=stepIndex++;
      const buttons=index<75?[{link:index<51?"https://example.invalid/install":"client://import/{{SUBSCRIPTION_LINK}}",
       type:index<51?"external":"subscriptionLink",text:loc("Action"),svgIconKey:"ExternalLink"}]:[];
      return {title:loc("Step"),description:loc("Only synthetic text"),svgIconKey:"Plus",svgIconColor:"#fff",buttons};
     })
    };
   })
  }])),
  baseTranslations:Object.fromEntries(Array.from({length:20},(_,i)=>["key"+i,loc("Value")])),
  svgLibrary:Object.fromEntries(Array.from({length:38},(_,i)=>["Demo"+i,"<svg/>"])),
 };
 const decoded=parsePageConfig(JSON.stringify(config));
 assert.deepEqual(decoded,config);
 assert.deepEqual(summary(decoded),{languages:5,platforms:7,apps:24,uniqueClients:10,blocks:92,buttons:75,icons:38});
 const inv=instructionInventory(decoded);
 assert.deepEqual(inv.platforms.map(p=>p.key),platformKeys);
 assert.equal(inv.languages,5);assert.equal(inv.appSlots,24);assert.equal(inv.blocks,92);assert.equal(inv.buttons,75);
 assert.deepEqual(inv.byType,{external:51,subscriptionLink:24,copyButton:0});
 assert.equal(inv.platforms.reduce((sum,p)=>sum+p.blocks,0),92);
 assert.equal(inv.platforms.reduce((sum,p)=>sum+p.buttons,0),75);
 const report=JSON.stringify(inv);
 assert.ok(!report.includes("https://")&&!report.includes("client://")&&!report.includes("{{SUBSCRIPTION_LINK}}"));
 const withCopy=structuredClone(decoded);
 withCopy.platforms.ios.apps[0].blocks[0].buttons[0].type="copyButton";
 const copyReport=instructionInventory(withCopy);
 assert.equal(copyReport.byType.copyButton,1);
 assert.equal(copyReport.byType.external,50);
});
