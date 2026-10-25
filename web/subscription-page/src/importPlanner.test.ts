import test from "node:test";
import assert from "node:assert/strict";
import {planClientImport, type ImportCapability} from "./importPlanner.ts";
const verified: ImportCapability = {platform:"ios",client:"Synthetic VPN",verified:true,supportsHandoff:true,supportsCopy:true,supportsQr:true};
test("default-off and absent attestation block every action",()=>{
 assert.equal(planClientImport(verified,"browser").state,"blocked");
 assert.equal(planClientImport(null,"browser",true).state,"blocked");
 assert.equal(planClientImport({...verified,verified:false},"browser",true).state,"blocked");
 assert.equal(planClientImport({...verified,platform:"unknown"},"browser",true).state,"blocked");
 assert.equal(planClientImport({...verified,client:" "},"browser",true).state,"blocked");
});
test("WebView never advertises a custom-scheme launch",()=>{
 assert.deepEqual(planClientImport(verified,"telegram-webview",true),{
  state:"manual-only",handoff:false,copy:true,qr:true,reason:"webview-fallback",
 });
});
test("browser handoff is a user-gesture candidate, with manual fallback",()=>{
 assert.deepEqual(planClientImport(verified,"browser",true),{
  state:"handoff-candidate",handoff:"requires-user-gesture",copy:true,qr:true,reason:"browser-fallback",
 });
});
test("no verified fallback means blocked even with handoff",()=>{
 assert.deepEqual(planClientImport({...verified,supportsCopy:false,supportsQr:false},"browser",true),{
  state:"blocked",handoff:false,copy:false,qr:false,reason:"no-fallback",
 });
});
test("copy and QR remain independently gated",()=>{
 const result=planClientImport({...verified,supportsHandoff:false,supportsQr:false},"browser",true);
 assert.equal(result.state,"manual-only");
 assert.equal(result.copy,true);
 assert.equal(result.qr,false);
 assert.equal(result.handoff,false);
});
