import test from "node:test";
import assert from "node:assert/strict";
import { requestManualImport, copyManualImportOnGesture, ManualImportUnavailable, type ManualImportInput } from "./manualImportClient.ts";

const origin="https://subscription.example.invalid";
const bearer=origin+"/sub/SYNTHETIC_SECRET";
const approved={platform:"ios",clientId:"synthetic-client",clientVersion:"1.0.0",reviewId:"#887",
  supportsHandoff:true,supportsCopy:true,supportsQr:true};
const defaults: ManualImportInput={platform:"ios",clientId:"synthetic-client",
  clientVersion:"1.0.0",context:"telegram-webview",method:"copy",
  enabled:true,expectedSubscriptionOrigin:origin,reviewed:[approved]};
const response=(data:unknown,status=200)=>
  new Response(JSON.stringify(data),{status,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
const csrf="a".repeat(64);
const proof="b".repeat(43);
const png=Uint8Array.from([137,80,78,71,13,10,26,10,1,2,3,4]);
function mockTransport(delivered:Response=response({subscriptionUrl:bearer})) {
 const requests:{path:string;init:RequestInit}[]=[];
 const transport=async(path:string,init:RequestInit):Promise<Response>=>{
  requests.push({path,init});
  if(path.endsWith("/csrf"))return response({csrfToken:csrf});
  if(path.endsWith("/issue"))return response({proof,expiresIn:45});
  return delivered;
 };
 return {transport,requests};
}

test("shipping without attestation / disabled pilot never initiates network",async()=>{
 for(const input of [
   {...defaults,enabled:false},{...defaults,reviewed:[]},
   {...defaults,clientVersion:"2.0.0"},
   {...defaults,expectedSubscriptionOrigin:"http://subscription.example.invalid"},
   {...defaults,method:"handoff" as "copy"},
 ]) {
  const m=mockTransport();
  await assert.rejects(()=>requestManualImport(input,m.transport),ManualImportUnavailable);
  assert.equal(m.requests.length,0);
 }
});

test("verified copy is one explicit three-step same-origin request, WebView never launches app",async()=>{
 const m=mockTransport();
 const result=await requestManualImport(defaults,m.transport);
 assert.deepEqual(result,{method:"copy",url:bearer});
 assert.deepEqual(m.requests.map(r=>r.path),[
  "/api/subpage/v1/import/preflight/csrf",
  "/api/subpage/v1/import/preflight/issue",
  "/api/subpage/v1/import/preflight/deliver"]);
 assert.deepEqual(m.requests.map(r=>r.init.method),["GET","POST","POST"]);
 for(const {init} of m.requests){
  assert.equal(init.credentials,"same-origin");assert.equal(init.cache,"no-store");
  assert.equal(init.redirect,"error");assert.equal(init.referrerPolicy,"no-referrer");
 }
 const body=JSON.parse(m.requests[2].init.body as string);
 assert.deepEqual(body,{proof,platform:"ios",clientId:"synthetic-client",
   clientVersion:"1.0.0",method:"copy"});
 assert.equal(JSON.stringify(m.requests).includes(bearer),false);
});

test("QR returns ephemeral PNG bytes, not a bearer URL string",async()=>{
 const m=mockTransport(new Response(png,{status:200,headers:{"Content-Type":"image/png"}}));
 const result=await requestManualImport({...defaults,method:"qr"},m.transport);
 assert.equal(result.method,"qr");
 if(result.method!=="qr")throw new Error("wrong result");
 assert.equal(result.png.type,"image/png");
 assert.deepEqual(new Uint8Array(await result.png.arrayBuffer()),png);
 assert.equal(JSON.parse(m.requests[2].init.body as string).method,"qr");
});

test("Copy and QR must each be approved separately",async()=>{
 const client={...approved,supportsCopy:false,supportsQr:true};
 const m=mockTransport();
 await assert.rejects(()=>requestManualImport({...defaults,reviewed:[client]},m.transport),ManualImportUnavailable);
 assert.equal(m.requests.length,0);
 const c={...approved,supportsCopy:true,supportsQr:false};
 await assert.rejects(()=>requestManualImport({...defaults,reviewed:[c],method:"qr"},m.transport),ManualImportUnavailable);
 assert.equal(m.requests.length,0);
});

test("server cannot inject another bearer origin, redirect, query controls or error details",async()=>{
 for(const url of ["http://subscription.example.invalid/sub/id",
  "https://evil.example.invalid/sub/id",origin+"/sub/id#fragment",
  origin+"/sub/id%0aheader",origin+"/sub/with space"]) {
  const m=mockTransport(response({subscriptionUrl:url}));
  await assert.rejects(()=>requestManualImport(defaults,m.transport),ManualImportUnavailable);
 }
 for(const delivered of [
  response({subscriptionUrl:bearer},403),
  new Response("secret private", {status:500}),
  new Response("moved",{status:302,headers:{Location:bearer}}),
  new Response("wrong content type",{status:200,headers:{"Content-Type":"text/plain"}}),
 ]) {
  const m=mockTransport(delivered);
  await assert.rejects(()=>requestManualImport(defaults,m.transport),ManualImportUnavailable);
 }
});

test("malformed CSRF, proof and QR are rejected fail-closed",async()=>{
 const calls:{path:string}[]=[];
 const badCsrf=async(path:string)=>{calls.push({path});return response({csrfToken:"wrong"});};
 await assert.rejects(()=>requestManualImport(defaults,badCsrf),ManualImportUnavailable);
 assert.equal(calls.length,1);
 const badProof=async(path:string)=>path.endsWith("/csrf")?response({csrfToken:csrf}):response({proof:"bad",expiresIn:45});
 await assert.rejects(()=>requestManualImport(defaults,badProof),ManualImportUnavailable);
 for(const qr of [new Response("not png",{status:200,headers:{"Content-Type":"image/png"}}),
     new Response(png,{status:200,headers:{"Content-Type":"text/plain"}})]) {
  const m=mockTransport(qr);
  await assert.rejects(()=>requestManualImport({...defaults,method:"qr"},m.transport),ManualImportUnavailable);
 }
});


test("D3i ClipboardItem write is enqueued inside the gesture before network",async()=>{
 const m=mockTransport();
 const steps:string[]=[];
 let copied="";
 await copyManualImportOnGesture(defaults,async(path,init)=>{
   steps.push(path);
   return m.transport(path,init);
 },content=>{
   // This callback is synchronous, emulating new ClipboardItem + clipboard.write.
   steps.push("clipboard.write");
   return content.then(async blob=>{copied=await blob.text();});
 });
 assert.equal(steps[0],"clipboard.write");
 assert.equal(steps[1],"/api/subpage/v1/import/preflight/csrf");
 assert.equal(copied,bearer);
 assert.equal(m.requests.length,3);
});

test("D3i clipboard refusal before fetch or stale selection never exposes bearer",async()=>{
 const m=mockTransport();
 await assert.rejects(()=>copyManualImportOnGesture(defaults,m.transport,()=>{
   throw new Error("sensitive clipboard error");
 }),ManualImportUnavailable);
 assert.equal(m.requests.length,0);

 let used=false;
 const stale=mockTransport();
 await assert.rejects(()=>copyManualImportOnGesture(defaults,async(path,init)=>{
   const result=await stale.transport(path,init);
   if(path.endsWith("/deliver"))used=true;
   return result;
 },content=>content.then(()=>{ throw new Error("must not reach clipboard"); }),()=>!used),
 ManualImportUnavailable);
 assert.equal(stale.requests.length,3);

 const invalid=mockTransport(response({subscriptionUrl:"https://evil.example.invalid/sub/PRIVATE"}));
 let leaked=false;
 await assert.rejects(()=>copyManualImportOnGesture(defaults,invalid.transport,
   content=>content.then(()=>{leaked=true;})),ManualImportUnavailable);
 assert.equal(leaked,false);
});

test("D3i clipboard rejection stays generic and never logs bearer",async()=>{
 const m=mockTransport();
 let wrote=false;
 await assert.rejects(()=>copyManualImportOnGesture(defaults,m.transport,
   content=>content.then(()=>{wrote=true; throw new Error("clipboard permission with SECRET");})),
 ManualImportUnavailable);
 assert.equal(wrote,true);
});
