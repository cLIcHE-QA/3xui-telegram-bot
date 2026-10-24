/**
 * #887 D2a: client transport for the isolated, pilot-only Telegram Mini App API.
 *
 * Only the signed *raw* Telegram.WebApp.initData is sent, in a JSON POST body.
 * Never use initDataUnsafe, URL parameters, local/session storage or a customer
 * subscription URL as identity. The server remains the authority for ownership.
 */
export const CUSTOMER_API = "/api/subpage/v1";
const MAX_INIT_DATA_BYTES = 8192;
const STATUSES = new Set(["active", "disabled", "expired", "suspended", "provisioning", "unknown"]);

export type CustomerSummary = Readonly<{
  status: string;
  periodStatus: string;
  planName: string;
  expiryTime: number | null;
  availableLocations: number | null;
}>;

export class MiniAppSessionError extends Error {
  constructor() { super("Не удалось подтвердить доступ через Telegram"); this.name = "MiniAppSessionError"; }
}

type FetchLike = (url: string, init: RequestInit) => Promise<Response>;

const SAFE_REQUEST: Pick<RequestInit, "credentials" | "cache" | "mode" | "redirect" | "referrerPolicy"> = {
  credentials: "same-origin",
  cache: "no-store",
  mode: "same-origin",
  redirect: "error",
  referrerPolicy: "no-referrer",
};

function validInitData(raw: unknown): raw is string {
  if (typeof raw !== "string" || raw.length === 0) return false;
  // UTF-8 bound mirrors the server and rejects controls before network I/O.
  return new TextEncoder().encode(raw).length <= MAX_INIT_DATA_BYTES && !/[\u0000-\u001f\u007f]/.test(raw);
}

/** Read only the raw string; never consult Telegram.WebApp.initDataUnsafe. */
export function readTelegramInitData(host: unknown): string | null {
  if (host === null || typeof host !== "object") return null;
  const telegram = (host as { Telegram?: { WebApp?: { initData?: unknown } } }).Telegram;
  const raw = telegram?.WebApp?.initData;
  return validInitData(raw) ? raw : null;
}

/** Strictly narrow a customer DTO; discard any unexpected bearer fields. */
export function safeCustomerSummary(input: unknown): CustomerSummary {
  if (input === null || typeof input !== "object" || Array.isArray(input)) throw new MiniAppSessionError();
  const body = (input as { subscription?: unknown }).subscription;
  if (body === null || typeof body !== "object" || Array.isArray(body)) throw new MiniAppSessionError();
  const dto = body as Record<string, unknown>;
  if (typeof dto.status !== "string" || !STATUSES.has(dto.status)
      || typeof dto.periodStatus !== "string" || dto.periodStatus.length > 40
      || typeof dto.planName !== "string" || dto.planName.length > 128) {
    throw new MiniAppSessionError();
  }
  const expiry = dto.expiryTime;
  const locations = dto.availableLocations;
  if (expiry !== null && (!Number.isSafeInteger(expiry) || (expiry as number) < 0 || (expiry as number) > 8_640_000_000_000_000)) throw new MiniAppSessionError();
  if (locations !== null && (!Number.isSafeInteger(locations) || (locations as number) < 0 || (locations as number) > 1000)) {
    throw new MiniAppSessionError();
  }
  return {
    status: dto.status,
    periodStatus: dto.periodStatus,
    planName: dto.planName,
    expiryTime: expiry as number | null,
    availableLocations: locations as number | null,
  };
}

async function responseJson(response: Response): Promise<unknown> {
  if (!response.ok || response.redirected) throw new MiniAppSessionError();
  const contentType = response.headers.get("content-type") || "";
  if (!/^application\/json(?:\s*;|$)/i.test(contentType)) throw new MiniAppSessionError();
  try { return await response.json(); } catch { throw new MiniAppSessionError(); }
}

/** Deliberate action: no automatic request on page load or StrictMode mount. */
export async function loginMiniApp(rawInitData: string, transport: FetchLike): Promise<CustomerSummary> {
  if (!validInitData(rawInitData)) throw new MiniAppSessionError();
  try {
    const login = await transport(CUSTOMER_API + "/auth/telegram", {
      ...SAFE_REQUEST,
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ initData: rawInitData }),
    });
    const session = await responseJson(login);
    if (session === null || typeof session !== "object"
        || (session as Record<string, unknown>).authenticated !== true
        || (session as Record<string, unknown>).mode !== "telegram") throw new MiniAppSessionError();
    const profile = await transport(CUSTOMER_API + "/me", {
      ...SAFE_REQUEST, method: "GET", headers: { "Accept": "application/json" },
    });
    return safeCustomerSummary(await responseJson(profile));
  } catch {
    // Never expose initData, a signed field, a request URL or server error text.
    throw new MiniAppSessionError();
  }
}

export async function logoutMiniApp(transport: FetchLike): Promise<boolean> {
  try {
    const response = await transport(CUSTOMER_API + "/logout", {
      ...SAFE_REQUEST, method: "POST", headers: { "Accept": "application/json" },
    });
    const body = await responseJson(response);
    return body !== null && typeof body === "object"
      && (body as Record<string, unknown>).authenticated === false;
  } catch {
    return false; // Unknown outcome, not a claimed successful logout.
  }
}
