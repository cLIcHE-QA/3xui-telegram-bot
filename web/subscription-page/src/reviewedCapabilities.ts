import { planClientImport, type ImportCapability, type ImportPlan } from "./importPlanner.ts";

/**
 * D3c offline capability evidence boundary.
 * Browser config, client names, SVG assets and user-selected platform are never
 * authority to mark a client verified. Only reviewed build-time evidence may be
 * supplied by a trusted caller; this module ships with an empty allowlist.
 */
export type ReviewedCapability = Readonly<{
  platform: string;
  clientId: string;
  clientVersion: string;
  reviewId: string;
  supportsHandoff: boolean;
  supportsCopy: boolean;
  supportsQr: boolean;
}>;
export const REVIEWED_CLIENT_CAPABILITIES: readonly ReviewedCapability[] = Object.freeze([]);
const SUPPORTED = new Set(["ios","android","macos","windows","linux","appleTV","androidTV"]);
const IDENTIFIER = /^[a-z0-9][a-z0-9._-]{0,63}$/;
const REVIEW_ID = /^#[1-9][0-9]{0,7}$/;

export function resolveReviewedCapability(
  platform: string,
  clientId: string,
  clientVersion: string,
  evidence: readonly ReviewedCapability[] = REVIEWED_CLIENT_CAPABILITIES,
): ImportCapability | null {
  if (!SUPPORTED.has(platform) || !IDENTIFIER.test(clientId) ||
      !IDENTIFIER.test(clientVersion)) return null;
  // Never trust duplicate or conflicting attestations. Evidence must identify
  // the exact client/version/platform and a traceable review issue.
  const matches = evidence.filter(e =>
    e.platform === platform && e.clientId === clientId && e.clientVersion === clientVersion);
  if (matches.length !== 1) return null;
  const e = matches[0];
  if (!REVIEW_ID.test(e.reviewId) ||
      typeof e.supportsHandoff !== "boolean" ||
      typeof e.supportsCopy !== "boolean" ||
      typeof e.supportsQr !== "boolean" ||
      (!e.supportsCopy && !e.supportsQr)) return null;
  return {
    platform, client: clientId, verified: true,
    supportsHandoff: e.supportsHandoff,
    supportsCopy: e.supportsCopy,
    supportsQr: e.supportsQr,
  };
}

/** Offline decision only. Does not accept a URL or perform side effects. */
export function planReviewedImport(
  platform: string,
  clientId: string,
  clientVersion: string,
  context: "browser" | "telegram-webview",
  pilotEnabled = false,
  evidence: readonly ReviewedCapability[] = REVIEWED_CLIENT_CAPABILITIES,
): ImportPlan {
  return planClientImport(
    resolveReviewedCapability(platform, clientId, clientVersion, evidence),
    context, pilotEnabled,
  );
}
