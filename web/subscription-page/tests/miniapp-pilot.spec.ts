import { test, expect } from "@playwright/test";

test.describe("D2a opt-in — только синтетический browser smoke", () => {
  // Default build must never activate this suite's pilot UI.
  test.skip(process.env.VITE_D2A_PILOT_UI !== "true", "Пилотный интерфейс выключен по умолчанию");

  test("D2a opt-in: явный вход, DTO без bearer-данных, подтверждённый logout", async ({ page }) => {
    const raw = "auth_date=1800000000&user=%7B%22id%22%3A100001%7D&hash=TEST_SIGNED_FIXTURE";
    const serverCalls: { path: string; method: string; body: string | null }[] = [];
    await page.addInitScript(({ initData }) => {
      (window as Window & { Telegram?: object }).Telegram = {
        WebApp: { initData, initDataUnsafe: { user: { id: 999999 } } },
      };
    }, { initData: raw });
    await page.route("**/api/subpage/v1/**", async route => {
      const request = route.request();
      const url = new URL(request.url());
      serverCalls.push({ path: url.pathname, method: request.method(), body: request.postData() });
      const reply = (data: object) => route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "Cache-Control": "no-store" },
        body: JSON.stringify(data),
      });
      if (url.pathname.endsWith("/auth/telegram")) return reply({ authenticated: true, mode: "telegram" });
      if (url.pathname.endsWith("/me")) return reply({
        subscription: {
          status: "active", periodStatus: "active", planName: "Тестовый тариф",
          expiryTime: 1800086400000, availableLocations: 2,
          sub_id: "PRIVATE_KEY", url: "https://secret.example.invalid/compat/PRIVATE_KEY",
          adminRole: "owner",
        },
      });
      if (url.pathname.endsWith("/logout")) return reply({ authenticated: false });
      return route.abort();
    });
    await page.goto("/");
    const panel = page.getByTestId("d2a-mini-app-pilot");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("d2a-authorized-summary")).toHaveCount(0);
    expect(serverCalls).toEqual([]); // No automatic initData processing on mount.
    await panel.getByRole("button", { name: "Подтвердить доступ через Telegram" }).click();
    await expect(page.getByTestId("d2a-authorized-summary")).toContainText("Тестовый тариф");
    await expect(panel).toContainText("Активна");
    await expect(panel).not.toContainText("PRIVATE_KEY");
    await expect(panel).not.toContainText("secret.example.invalid");
    await expect(page.getByRole("button", { name: "Получить ссылку" })).toBeDisabled();
    expect(serverCalls.map(call => [call.path, call.method])).toEqual([
      ["/api/subpage/v1/auth/telegram", "POST"],
      ["/api/subpage/v1/me", "GET"],
    ]);
    expect(JSON.parse(serverCalls[0].body || "null")).toEqual({ initData: raw });
    expect(serverCalls[1].body).toBeNull();
    expect(serverCalls.every(call => !call.path.includes("hash") && !call.path.includes("token"))).toBe(true);
    await panel.getByRole("button", { name: "Выйти" }).click();
    await expect(page.getByTestId("d2a-authorized-summary")).toHaveCount(0);
    await expect(panel).toContainText("Выход подтверждён");
    expect(serverCalls[2]).toMatchObject({ path: "/api/subpage/v1/logout", method: "POST" });
  });

  test("D2a opt-in: без raw initData отказывает до любого запроса", async ({ page }) => {
    await page.addInitScript(() => {
      (window as Window & { Telegram?: object }).Telegram = { WebApp: { initDataUnsafe: { user: { id: 100001 } } } };
    });
    const calls: string[] = [];
    page.on("request", request => {
      if (request.url().includes("/api/subpage/v1/")) calls.push(request.url());
    });
    await page.goto("/");
    const panel = page.getByTestId("d2a-mini-app-pilot");
    await panel.getByRole("button", { name: "Подтвердить доступ через Telegram" }).click();
    await expect(panel).toContainText("Откройте эту страницу внутри поддерживаемого Telegram Mini App.");
    expect(calls).toEqual([]);
  });
});
