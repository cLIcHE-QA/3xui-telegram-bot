/** #887 D3a: inert client-import capability planner. No URLs, secrets or navigation. */
export type ImportCapability = Readonly<{
  platform: string;
  client: string;
  verified: boolean;
  supportsHandoff: boolean;
  supportsCopy: boolean;
  supportsQr: boolean;
}>;
export type ImportPlan = Readonly<{
  state: "blocked" | "manual-only" | "handoff-candidate";
  handoff: false | "requires-user-gesture";
  copy: boolean;
  qr: boolean;
  reason: "not-verified" | "no-fallback" | "webview-fallback" | "browser-fallback";
}>;
const PLATFORMS = new Set(["ios","android","macos","windows","linux","appleTV","androidTV"]);
/**
 * Plans *visibility only*, never constructs, reads, copies or opens a subscription URL.
 * A verified capability is an explicit external attestation, not inferred from a
 * client name, imported JSON button, platform or icon.
 */
export function planClientImport(
  capability: ImportCapability | null,
  context: "browser" | "telegram-webview",
  pilotEnabled = false,
): ImportPlan {
  const blocked: ImportPlan = {state:"blocked",handoff:false,copy:false,qr:false,reason:"not-verified"};
  if (!pilotEnabled || !capability || !PLATFORMS.has(capability.platform)
      || !capability.client.trim() || !capability.verified) return blocked;
  const copy = capability.supportsCopy === true;
  const qr = capability.supportsQr === true;
  if (!copy && !qr) return {...blocked,reason:"no-fallback"};
  // WebView custom schemes are unreliable; never present them as an executable action.
  if (context === "telegram-webview") return {
    state:"manual-only",handoff:false,copy,qr,reason:"webview-fallback",
  };
  if (capability.supportsHandoff === true) return {
    state:"handoff-candidate",handoff:"requires-user-gesture",copy,qr,reason:"browser-fallback",
  };
  return {state:"manual-only",handoff:false,copy,qr,reason:"browser-fallback"};
}
