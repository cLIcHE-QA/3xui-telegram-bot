import test from "node:test";
import assert from "node:assert/strict";
import {
  startStandalone, completeStandalone, cancelStandalone, logoutStandalone,
} from "./standaloneClient.ts";
import { MiniAppSessionError } from "./miniAppClient.ts";

const code = "abcdefghijklmnop";
const reply = (value: unknown, status = 200, type = "application/json") =>
  new Response(JSON.stringify(value), { status, headers: { "content-type": type } });

test("standalone start: only same-origin POST body {}; challenge is not a session", async () => {
  const calls: { path: string; options: RequestInit }[] = [];
  const transport = async (path: string, options: RequestInit) => {
    calls.push({ path, options });
    return reply({ challenge: code, expiresIn: 180, ownerId: 9999, subscriptionUrl: "secret" });
  };
  const start = await startStandalone(transport);
  assert.deepEqual(start, { challenge: code, expiresIn: 180 });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, "/api/subpage/v1/auth/standalone/start");
  assert.equal(calls[0].options.credentials, "same-origin");
  assert.equal(calls[0].options.referrerPolicy, "no-referrer");
  assert.equal(calls[0].options.cache, "no-store");
  assert.equal(calls[0].options.redirect, "error");
  assert.equal(calls[0].options.mode, "same-origin");
  assert.deepEqual(JSON.parse(String(calls[0].options.body)), {});
  assert.ok(!calls[0].path.includes("sub_id") && !calls[0].path.includes("telegram_id"));
});

test("manual complete: pending does not fetch profile or issue identity", async () => {
  let count = 0;
  const result = await completeStandalone(code, async (path, options) => {
    count++;
    assert.equal(path, "/api/subpage/v1/auth/standalone/complete");
    assert.deepEqual(JSON.parse(String(options.body)), { challenge: code });
    return reply({ state: "pending" }, 202);
  });
  assert.deepEqual(result, { state: "pending" });
  assert.equal(count, 1);
});

test("confirmed exchange reads safe DTO, not subscription bearer/admin data", async () => {
  const paths: string[] = [];
  const result = await completeStandalone(code, async (path, options) => {
    paths.push(path);
    assert.equal(options.credentials, "same-origin");
    if (paths.length === 1) {
      assert.deepEqual(JSON.parse(String(options.body)), { challenge: code });
      return reply({ state: "authenticated", mode: "standalone" });
    }
    assert.equal(options.method, "GET");
    assert.equal(options.body, undefined);
    return reply({
      subscription: {
        status: "active", periodStatus: "active",
        planName: "Тестовый", expiryTime: 1800086400000, availableLocations: 2,
        sub_id: "private", url: "https://private.invalid", adminRole: "owner",
      },
    });
  });
  assert.deepEqual(paths, ["/api/subpage/v1/auth/standalone/complete", "/api/subpage/v1/standalone/me"]);
  assert.deepEqual(result, {
    state: "authenticated",
    subscription: {
      status: "active", periodStatus: "active",
      planName: "Тестовый", expiryTime: 1800086400000, availableLocations: 2,
    },
  });
  assert.ok(paths.every(path => !path.includes(code) && !path.includes("private")));
});

test("forged/invalid/expired/missing challenges fail closed without leaking values", async () => {
  let network = 0;
  const transport = async () => {
    network++;
    return reply({ state: "authenticated", mode: "standalone" });
  };
  for (const bad of ["", "short", "ABC".repeat(100), "abc\u0000def", "test?telegram_id=1"]) {
    await assert.rejects(completeStandalone(bad, transport), MiniAppSessionError);
    assert.equal(await cancelStandalone(bad, transport), false);
  }
  assert.equal(network, 0);
  for (const bad of [
    { challenge: "", expiresIn: 180 },
    { challenge: "a".repeat(64), expiresIn: 180 },
    { challenge: code, expiresIn: 181 },
    { challenge: code, expiresIn: 12 },
    { challenge: code, expiresIn: "180" },
    { authenticated: true, mode: "standalone" },
  ]) {
    await assert.rejects(startStandalone(async () => reply(bad)), MiniAppSessionError);
  }
});

test("remote errors, responses with HTML, incorrect modes and malformed DTO are generic", async () => {
  for (const bad of [
    reply({ state: "authenticated", mode: "telegram" }),
    reply({ state: "denied" }, 403),
    reply({ error: code }, 500),
    reply({ state: "authenticated", mode: "standalone" }, 200, "text/html"),
  ]) {
    await assert.rejects(completeStandalone(code, async () => bad), error => {
      assert.ok(error instanceof MiniAppSessionError);
      assert.ok(!error.message.includes(code));
      return true;
    });
  }
  await assert.rejects(
    completeStandalone(code, async (path) => path.endsWith("/me")
      ? reply({ subscription: { sub_id: code, status: "active" } })
      : reply({ state: "authenticated", mode: "standalone" })),
    MiniAppSessionError,
  );
  await assert.rejects(
    completeStandalone(code, async () => { throw new Error("PRIVATE_" + code); }),
    MiniAppSessionError,
  );
});

test("cancel and logout never claim success without confirmed server response", async () => {
  assert.equal(await cancelStandalone(code, async (path, options) => {
    assert.equal(path, "/api/subpage/v1/auth/standalone/cancel");
    assert.deepEqual(JSON.parse(String(options.body)), { challenge: code });
    return reply({ state: "cancelled" });
  }), true);
  assert.equal(await cancelStandalone(code, async () => reply({ state: "authenticated" })), false);
  assert.equal(await logoutStandalone(async (path, options) => {
    assert.equal(path, "/api/subpage/v1/auth/standalone/logout");
    assert.deepEqual(JSON.parse(String(options.body)), {});
    return reply({ authenticated: false });
  }), true);
  assert.equal(await logoutStandalone(async () => reply({ authenticated: true })), false);
  assert.equal(await logoutStandalone(async () => reply({ authenticated: false }, 503)), false);
});
