import { test, expect } from "@playwright/test";

test.describe("D2b opt-in standalone owner proof — синтетический browser smoke", () => {
  test.skip(process.env.VITE_D2B_STANDALONE_PILOT_UI !== "true",
    "D2b test UI выключен в обычной сборке");

  test("D2b opt-in: без auto-login, явный challenge, pending, owner DTO, подтверждённый выход", async ({ page }) => {
    const challenge = "abcdefghijklmnop";
    const requests: { path: string; method: string; body: string | null }[] = [];
    let completions = 0;
    await page.route("**/api/subpage/v1/**", async route => {
      const req = route.request();
      const url = new URL(req.url());
      requests.push({ path: url.pathname, method: req.method(), body: req.postData() });
      const respond = (body: object, status = 200) => route.fulfill({
        status, contentType: "application/json",
        headers: { "Cache-Control": "no-store" },
        body: JSON.stringify(body),
      });
      if (url.pathname.endsWith("/standalone/start")) return respond({ challenge, expiresIn: 180 });
      if (url.pathname.endsWith("/standalone/complete")) {
        completions++;
        return completions === 1
          ? respond({ state: "pending" }, 202)
          : respond({ state: "authenticated", mode: "standalone" });
      }
      if (url.pathname.endsWith("/standalone/me")) {
        return respond({ subscription: {
          status: "active", periodStatus: "active", planName: "Тестовый тариф",
          expiryTime: 1800086400000, availableLocations: 2,
          sub_id: "SECRET_SUB_ID", bearerUrl: "https://private.invalid/compat/SECRET_SUB_ID",
          adminRole: "owner",
        } });
      }
      if (url.pathname.endsWith("/standalone/logout")) return respond({ authenticated: false });
      return route.abort();
    });
    await page.goto("/");
    const panel = page.getByTestId("d2b-standalone-pilot");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("d2a-mini-app-pilot")).toHaveCount(0);
    await expect(page.getByTestId("d2b-challenge")).toHaveCount(0);
    expect(requests).toEqual([]);
    await panel.getByRole("button", { name: "Создать запрос" }).click();
    await expect(page.getByTestId("d2b-challenge")).toHaveText(challenge);
    expect(requests.map(x => x.path)).toEqual(["/api/subpage/v1/auth/standalone/start"]);
    expect(requests[0].method).toBe("POST");
    expect(JSON.parse(requests[0].body || "null")).toEqual({});
    await panel.getByRole("button", { name: "Проверить подтверждение" }).click();
    await expect(panel).toContainText("Ожидается явное подтверждение");
    await expect(page.getByTestId("d2b-standalone-summary")).toHaveCount(0);
    await panel.getByRole("button", { name: "Проверить подтверждение" }).click();
    await expect(page.getByTestId("d2b-standalone-summary")).toContainText("Тестовый тариф");
    await expect(panel).not.toContainText("SECRET_SUB_ID");
    await expect(panel).not.toContainText("private.invalid");
    await expect(page.getByTestId("d2b-challenge")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Получить ссылку" })).toBeDisabled();
    expect(requests.map(x => x.path)).toEqual([
      "/api/subpage/v1/auth/standalone/start",
      "/api/subpage/v1/auth/standalone/complete",
      "/api/subpage/v1/auth/standalone/complete",
      "/api/subpage/v1/standalone/me",
    ]);
    expect(JSON.parse(requests[1].body || "null")).toEqual({ challenge });
    expect(requests[3].method).toBe("GET");
    expect(requests[3].body).toBeNull();
    expect(requests.every(x => !x.path.includes(challenge) && !x.path.includes("SECRET_SUB_ID"))).toBe(true);
    await panel.getByRole("button", { name: "Выйти" }).click();
    await expect(page.getByTestId("d2b-standalone-summary")).toHaveCount(0);
    await expect(panel).toContainText("Выход подтверждён");
    expect(requests.at(-1)?.path).toBe("/api/subpage/v1/auth/standalone/logout");
  });

  test("D2b opt-in: отмена подтверждается сервером, нет выдачи owner data", async ({ page }) => {
    let calls = 0;
    await page.route("**/api/subpage/v1/**", async route => {
      calls++;
      const path = new URL(route.request().url()).pathname;
      return route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify(path.endsWith("/start")
          ? { challenge: "abcdefghijklmnop", expiresIn: 180 }
          : { state: "cancelled" }),
      });
    });
    await page.goto("/");
    const panel = page.getByTestId("d2b-standalone-pilot");
    await panel.getByRole("button", { name: "Создать запрос" }).click();
    await expect(page.getByTestId("d2b-challenge")).toBeVisible();
    await panel.getByRole("button", { name: "Отменить запрос" }).click();
    await expect(page.getByTestId("d2b-challenge")).toHaveCount(0);
    await expect(panel).toContainText("Запрос отменён");
    await expect(page.getByTestId("d2b-standalone-summary")).toHaveCount(0);
    expect(calls).toBe(2);
  });
});
