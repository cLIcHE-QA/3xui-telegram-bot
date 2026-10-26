/** #887 D3g: manual Copy/QR, explicitly gated by reviewed capability and server proof.
 * Never auto-fetch on mount. No local/session storage, telemetry, redirects,
 * raw browser owner IDs or custom-scheme handoff (including Telegram WebView).
 */
import { planReviewedImport, type ReviewedCapability } from "./reviewedCapabilities.ts";

const BASE = "/api/subpage/v1/import/preflight";
const CSRF = /^[a-f0-9]{64}$/;
const PROOF = /^[A-Za-z0-9_-]{43}$/;
const CLIENT = /^[a-z0-9][a-z0-9._-]{0,63}$/;
const PNG_HEADER = [137,80,78,71,13,10,26,10];

export type ManualMethod = "copy" | "qr";
export type ManualImportInput = Readonly<{
  platform: string;
  clientId: string;
  clientVersion: string;
  context: "browser" | "telegram-webview";
  method: ManualMethod;
  enabled: boolean;
  expectedSubscriptionOrigin: string;
  reviewed: readonly ReviewedCapability[];
}>;
export type ManualResult = Readonly<
  | { method: "copy"; url: string }
  | { method: "qr"; png: Blob }
>;
type FetchLike = (path: string, options: RequestInit) => Promise<Response>;

export class ManualImportUnavailable extends Error {
  constructor() { super("Импорт недоступен: проверьте авторизацию и настройки клиента."); this.name = "ManualImportUnavailable"; }
}

function safeOrigin(raw: string): string | null {
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:" || url.username || url.password ||
        url.search || url.hash || url.pathname !== "/" ||
        url.origin !== raw) return null;
    return url.origin;
  } catch { return null; }
}

function validBearer(value: unknown, expectedOrigin: string): value is string {
  if (typeof value !== "string" || value.length < 12 || value.length > 2048 ||
      /[\u0000-\u0020\u007f\\{}]/.test(value) ||
      /%(?:0[0-9a-f]|1[0-9a-f]|7f|5c)/i.test(value)) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.origin === expectedOrigin &&
      !url.username && !url.password && !url.hash &&
      url.pathname !== "/" && url.href === value;
  } catch { return false; }
}

const REQUEST: Pick<RequestInit, "credentials"|"cache"|"mode"|"redirect"|"referrerPolicy"> = {
  credentials: "same-origin", cache: "no-store", mode: "same-origin",
  redirect: "error", referrerPolicy: "no-referrer",
};

async function json(response: Response): Promise<Record<string, unknown>> {
  if (!response.ok || response.redirected ||
      !/^application\/json(?:\s*;|$)/i.test(response.headers.get("content-type") || "")) {
    throw new ManualImportUnavailable();
  }
  try {
    const value: unknown = await response.json();
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    return value as Record<string, unknown>;
  } catch { throw new ManualImportUnavailable(); }
}

/** Call only on a deliberate action, never from effects or page loading. */
export async function requestManualImport(
  request: ManualImportInput,
  transport: FetchLike,
): Promise<ManualResult> {
  const origin = safeOrigin(request.expectedSubscriptionOrigin);
  if (!origin || !CLIENT.test(request.clientId) || !CLIENT.test(request.clientVersion) ||
      (request.method !== "copy" && request.method !== "qr")) throw new ManualImportUnavailable();
  const plan = planReviewedImport(request.platform, request.clientId,
    request.clientVersion, request.context, request.enabled, request.reviewed);
  if (plan.state === "blocked" || (request.method === "copy" ? !plan.copy : !plan.qr)) {
    throw new ManualImportUnavailable();
  }

  try {
    const tokenResponse = await json(await transport(BASE + "/csrf", {
      ...REQUEST, method: "GET", headers: {Accept:"application/json"},
    }));
    if (typeof tokenResponse.csrfToken !== "string" || !CSRF.test(tokenResponse.csrfToken)) {
      throw new ManualImportUnavailable();
    }
    const csrf = tokenResponse.csrfToken;
    const issue = await json(await transport(BASE + "/issue", {
      ...REQUEST, method: "POST",
      headers: {Accept:"application/json", "Content-Type":"application/json", "X-CSRF-Token":csrf},
      body: JSON.stringify({}),
    }));
    if (typeof issue.proof !== "string" || !PROOF.test(issue.proof) || issue.expiresIn !== 45) {
      throw new ManualImportUnavailable();
    }
    const response = await transport(BASE + "/deliver", {
      ...REQUEST, method: "POST",
      headers: {Accept:request.method === "qr" ? "image/png" : "application/json",
        "Content-Type":"application/json", "X-CSRF-Token":csrf},
      body: JSON.stringify({proof:issue.proof, platform:request.platform,
        clientId:request.clientId, clientVersion:request.clientVersion,
        method:request.method}),
    });
    if (request.method === "copy") {
      const delivered = await json(response);
      if (!validBearer(delivered.subscriptionUrl, origin)) throw new ManualImportUnavailable();
      return {method:"copy", url:delivered.subscriptionUrl};
    }
    if (!response.ok || response.redirected ||
        !/^image\/png(?:\s*;|$)/i.test(response.headers.get("content-type") || "")) {
      throw new ManualImportUnavailable();
    }
    const size = Number(response.headers.get("content-length") || 0);
    if (!Number.isFinite(size) || size > 131072) throw new ManualImportUnavailable();
    const png = await response.arrayBuffer();
    const bytes = new Uint8Array(png);
    if (bytes.length <= PNG_HEADER.length || bytes.length > 131072 ||
        !PNG_HEADER.every((value,index)=>bytes[index] === value)) throw new ManualImportUnavailable();
    return {method:"qr", png:new Blob([png], {type:"image/png"})};
  } catch {
    // Never surface bearer URLs, session cookies, upstream exception text or proof.
    throw new ManualImportUnavailable();
  }
}


/**
 * D3i: reserve ClipboardItem AS PART OF THE CLICK, before first await/fetch.
 * Safari/WebView may lose user activation during csrf/issue/deliver.
 * A pending ClipboardItem Blob resolves only after owner-bound delivery
 * and rejects on auth failure or changed client selection.
 * Caller synchronously calls navigator.clipboard.write inside enqueue.
 * Unsupported browsers offer reviewed QR, never delayed writeText.
 */
export async function copyManualImportOnGesture(
  request: Omit<ManualImportInput, "method">,
  transport: FetchLike,
  enqueue: (content: Promise<Blob>) => Promise<void>,
  stillCurrent: () => boolean = () => true,
): Promise<void> {
  let accept!: (blob: Blob) => void;
  let refuse!: (error: Error) => void;
  const content = new Promise<Blob>((resolve, reject) => {
    accept = resolve;
    refuse = reject;
  });
  // Avoid unhandled rejections when clipboard.write rejects early.
  void content.catch(() => {});
  let writing: Promise<void>;
  try {
    writing = enqueue(content); // synchronous before ANY authorization await
  } catch {
    refuse(new ManualImportUnavailable());
    throw new ManualImportUnavailable();
  }
  void writing.catch(() => {});
  try {
    const result = await requestManualImport(
      {...request, method: "copy"}, transport,
    );
    if (!stillCurrent() || result.method !== "copy") {
      throw new ManualImportUnavailable();
    }
    accept(new Blob([result.url], {type: "text/plain"}));
    await writing;
  } catch {
    refuse(new ManualImportUnavailable());
    throw new ManualImportUnavailable();
  }
}
