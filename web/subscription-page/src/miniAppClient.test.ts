import test from "node:test";
import assert from "node:assert/strict";
import {
  CUSTOMER_API, MiniAppSessionError, loginMiniApp, logoutMiniApp,
  readTelegramInitData, safeCustomerSummary,
} from "./miniAppClient.ts";

const signed = "auth_date=1800000000&user=%7B%22id%22%3A100001%7D&hash=synthetic";

const response = (body: unknown, code = 200) => new Response(JSON.stringify(body), {
  status: code, headers: { "content-type": "application/json; charset=utf-8" },
});
const minimal = {
  subscription: {
    status: "active", periodStatus: "active", planName: "Тестовый тариф",
    expiryTime: 1800086400000, availableLocations: 2,
  },
};

test("читать только raw Telegram initData без initDataUnsafe, URL и хранения", () => {
  assert.equal(readTelegramInitData({ Telegram: { WebApp: { initData: signed, initDataUnsafe: { user: { id: 999 } } } } }), signed);
  assert.equal(readTelegramInitData({ Telegram: { WebApp: { initDataUnsafe: { user: { id: 100001 } } } } }), null);
  assert.equal(readTelegramInitData({ Telegram: { WebApp: { initData: "" } } }), null);
  assert.equal(readTelegramInitData({ Telegram: { WebApp: { initData: "x".repeat(8193) } } }), null);
  assert.equal(readTelegramInitData({ Telegram: { WebApp: { initData: signed + "\n" } } }), null);
  assert.equal(readTelegramInitData(null), null);
});

test("явный вход отправляет raw initData только в POST body и затем считывает безопасный DTO", async () => {
  const calls: { path: string; request: RequestInit }[] = [];
  const request = async (path: string, init: RequestInit): Promise<Response> => {
    calls.push({ path, request: init });
    return path.endsWith("/auth/telegram")
      ? response({ authenticated: true, mode: "telegram" })
      : response({ ...minimal, bearerUrl: "https://secret.invalid/compat/private", email: "private@example.invalid" });
  };
  const summary = await loginMiniApp(signed, request);
  assert.deepEqual(summary, minimal.subscription);
  assert.equal(calls.length, 2);
  assert.deepEqual(calls.map(c => c.path), [CUSTOMER_API + "/auth/telegram", CUSTOMER_API + "/me"]);
  assert.equal(calls[0].request.method, "POST");
  assert.equal(calls[1].request.method, "GET");
  for (const { path, request: options } of calls) {
    assert.ok(!path.includes("initData") && !path.includes("hash=") && !path.includes("secret"));
    assert.equal(options.credentials, "same-origin");
    assert.equal(options.cache, "no-store");
    assert.equal(options.mode, "same-origin");
    assert.equal(options.redirect, "error");
    assert.equal(options.referrerPolicy, "no-referrer");
    assert.ok(!JSON.stringify(options.headers || {}).includes("Authorization"));
  }
  assert.deepEqual(JSON.parse(String(calls[0].request.body)), { initData: signed });
  assert.equal(calls[1].request.body, undefined);
});

test("отказ от неподписанных или слишком больших входных данных до fetch", async () => {
  let called = 0;
  const forbidden = async (): Promise<Response> => { called++; return response({}); };
  for (const payload of ["", signed + "\u0000", "a".repeat(10000)]) {
    await assert.rejects(loginMiniApp(payload, forbidden), MiniAppSessionError);
  }
  assert.equal(called, 0);
});

test("неизвестные DTO поля не становятся полномочиями, нет IDOR и утечек", () => {
  assert.deepEqual(safeCustomerSummary({
    ...minimal,
    subscription: { ...minimal.subscription, sub_id: "private", url: "https://private.invalid", adminRole: "owner", keys: ["key"] },
  }), minimal.subscription);
  for (const bad of [
    {}, null, { subscription: null },
    { subscription: { ...minimal.subscription, status: "alien" } },
    { subscription: { ...minimal.subscription, planName: null } },
    { subscription: { ...minimal.subscription, periodStatus: null } },
    { subscription: { ...minimal.subscription, expiryTime: -1 } },
    { subscription: { ...minimal.subscription, availableLocations: "4" } },
    { subscription: { ...minimal.subscription, availableLocations: 2000 } },
  ]) {
    assert.throws(() => safeCustomerSummary(bad), MiniAppSessionError);
  }
});

test("ошибка auth, неверный Content-Type и невалидный DTO дают только общую ошибку без signed данных", async () => {
  const badServers = [
    async () => response({ authenticated: false, mode: "telegram" }),
    async () => response({ authenticated: true, mode: "standalone" }),
    async () => response({ error: signed }, 401),
    async () => new Response("redirect", { status: 302 }),
    async () => new Response("<html>private</html>", { status: 200, headers: { "content-type": "text/html" } }),
    async () => response({ authenticated: true, mode: "telegram" }),
  ];
  for (let i = 0; i < badServers.length; i++) {
    let calls = 0;
    const service = async (): Promise<Response> => {
      calls++;
      if (i === 5 && calls === 2) return response({ subscription: { status: "active", sub_id: signed } });
      return badServers[i]();
    };
    await assert.rejects(loginMiniApp(signed, service), error => {
      assert.ok(error instanceof MiniAppSessionError);
      assert.ok(!error.message.includes(signed));
      assert.ok(!error.message.includes("private"));
      return true;
    });
  }
});

test("logout утверждается только после подтверждённого backend ack", async () => {
  let calls = 0;
  const good = async (path: string, options: RequestInit): Promise<Response> => {
    calls++;
    assert.equal(path, CUSTOMER_API + "/logout");
    assert.equal(options.method, "POST");
    assert.equal(options.credentials, "same-origin");
    assert.equal(options.referrerPolicy, "no-referrer");
    return response({ authenticated: false });
  };
  assert.equal(await logoutMiniApp(good), true);
  assert.equal(calls, 1);
  assert.equal(await logoutMiniApp(async () => response({ authenticated: true })), false);
  assert.equal(await logoutMiniApp(async () => response({ authenticated: false }, 503)), false);
  assert.equal(await logoutMiniApp(async () => { throw new Error(signed); }), false);
});
