/**
 * #887 D2b: explicit browser-bound standalone challenge exchange (pilot only).
 *
 * Challenge text is NOT an authenticator; a verified PRIVATE bot interaction must
 * separately approve it. The browser cannot approve its own challenge.
 * No persistent storage, URL query fragments, redirects or subscriber bearer IDs.
 */
import { MiniAppSessionError, safeCustomerSummary, type CustomerSummary } from "./miniAppClient.ts";

const API = "/api/subpage/v1/auth/standalone";
const PROFILE = "/api/subpage/v1/standalone/me";
const CODE = /^[A-Za-z0-9_-]{16}$/;
type FetchLike = (path: string, options: RequestInit) => Promise<Response>;
const SAFE: Pick<RequestInit, "credentials" | "cache" | "mode" | "redirect" | "referrerPolicy"> = {
  credentials: "same-origin",
  cache: "no-store",
  mode: "same-origin",
  redirect: "error",
  referrerPolicy: "no-referrer",
};

function request(method: string, body?: Record<string, unknown>): RequestInit {
  return {
    ...SAFE,
    method,
    headers: { "Accept": "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  };
}

async function json(response: Response, expectedStatus: number): Promise<unknown> {
  if (response.status !== expectedStatus || response.redirected
      || !/^application\/json(?:\s*;|$)/i.test(response.headers.get("content-type") || "")) {
    throw new MiniAppSessionError();
  }
  try { return await response.json(); } catch { throw new MiniAppSessionError(); }
}

function assertChallenge(challenge: unknown): asserts challenge is string {
  if (typeof challenge !== "string" || !CODE.test(challenge)) throw new MiniAppSessionError();
}

export type StandaloneStart = Readonly<{ challenge: string; expiresIn: number }>;
export type StandaloneCompletion =
  | Readonly<{ state: "pending" }>
  | Readonly<{ state: "authenticated"; subscription: CustomerSummary }>;

export async function startStandalone(transport: FetchLike): Promise<StandaloneStart> {
  try {
    const payload = await json(await transport(API + "/start", request("POST", {})), 200);
    if (!payload || typeof payload !== "object") throw new MiniAppSessionError();
    const object = payload as Record<string, unknown>;
    assertChallenge(object.challenge);
    if (!Number.isSafeInteger(object.expiresIn) || (object.expiresIn as number) < 30
        || (object.expiresIn as number) > 180) throw new MiniAppSessionError();
    return { challenge: object.challenge, expiresIn: object.expiresIn as number };
  } catch {
    throw new MiniAppSessionError();
  }
}

export async function completeStandalone(challenge: string, transport: FetchLike): Promise<StandaloneCompletion> {
  assertChallenge(challenge);
  try {
    const response = await transport(API + "/complete", request("POST", { challenge }));
    if (response.status === 202) {
      const result = await json(response, 202);
      if (!result || typeof result !== "object" || (result as Record<string, unknown>).state !== "pending") {
        throw new MiniAppSessionError();
      }
      return { state: "pending" };
    }
    const result = await json(response, 200);
    if (!result || typeof result !== "object"
        || (result as Record<string, unknown>).state !== "authenticated"
        || (result as Record<string, unknown>).mode !== "standalone") throw new MiniAppSessionError();
    const profile = await transport(PROFILE, request("GET"));
    return { state: "authenticated", subscription: safeCustomerSummary(await json(profile, 200)) };
  } catch {
    // Never include challenge, subscription URL or server error in the UI.
    throw new MiniAppSessionError();
  }
}

export async function cancelStandalone(challenge: string, transport: FetchLike): Promise<boolean> {
  if (!CODE.test(challenge)) return false;
  try {
    const data = await json(await transport(API + "/cancel", request("POST", { challenge })), 200);
    return !!data && typeof data === "object" && (data as Record<string, unknown>).state === "cancelled";
  } catch { return false; }
}

export async function logoutStandalone(transport: FetchLike): Promise<boolean> {
  try {
    const data = await json(await transport(API + "/logout", request("POST", {})), 200);
    return !!data && typeof data === "object" && (data as Record<string, unknown>).authenticated === false;
  } catch { return false; }
}
