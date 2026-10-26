import test from "node:test";
import assert from "node:assert/strict";
import { planReviewedImport, resolveReviewedCapability } from "./reviewedCapabilities.ts";
const approved = {platform:"ios",clientId:"synthetic-client",clientVersion:"1.0.0",reviewId:"#887",
  supportsHandoff:true,supportsCopy:true,supportsQr:true};
test("empty shipping allowlist fails closed even with pilot",()=>{
 assert.equal(resolveReviewedCapability("ios","synthetic-client","1.0.0"),null);
 assert.equal(planReviewedImport("ios","synthetic-client","1.0.0","browser",true).state,"blocked");
});
test("exact reviewed evidence required for every platform, client and version",()=>{
 assert.equal(resolveReviewedCapability("android","synthetic-client","1.0.0",[approved]),null);
 assert.equal(resolveReviewedCapability("ios","other-client","1.0.0",[approved]),null);
 assert.equal(resolveReviewedCapability("ios","synthetic-client","2.0.0",[approved]),null);
 assert.equal(resolveReviewedCapability("ios","synthetic-client","1.0.0",[approved])?.verified,true);
 assert.equal(planReviewedImport("ios","synthetic-client","1.0.0","browser",false,[approved]).state,"blocked");
});
test("WebView disallows handoff even with synthetic reviewed capability",()=>{
 const plan=planReviewedImport("ios","synthetic-client","1.0.0","telegram-webview",true,[approved]);
 assert.equal(plan.state,"manual-only");assert.equal(plan.handoff,false);
 assert.equal(plan.copy,true);assert.equal(plan.qr,true);
});
test("duplicate, malformed and fallback-less attestations fail closed",()=>{
 assert.equal(resolveReviewedCapability("ios","synthetic-client","1.0.0",[approved,approved]),null);
 assert.equal(resolveReviewedCapability("ios","synthetic-client","1.0.0",[{...approved,reviewId:"unreviewed"}]),null);
 assert.equal(resolveReviewedCapability("ios","synthetic-client","1.0.0",[{...approved,supportsCopy:false,supportsQr:false}]),null);
 assert.equal(resolveReviewedCapability("ios","synthetic-client","1.0.0",[{...approved,supportsCopy:"yes" as unknown as boolean}]),null);
 assert.equal(resolveReviewedCapability("ios","SYNTHETIC-CLIENT","1.0.0",[approved]),null);
 assert.equal(resolveReviewedCapability("ios","synthetic-client","../bad",[approved]),null);
});
