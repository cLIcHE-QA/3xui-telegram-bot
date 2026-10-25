import { test, expect } from "@playwright/test";

test.describe("D2d staging opt-in — синтетическая сверка полного кода и origin", () => {
  test.skip(
    process.env.VITE_D2B_STANDALONE_PILOT_UI !== "true"
      || process.env.VITE_D2D_STAGING_UI !== "true",
    "Staging UX выключен в обычной сборке",
  );

  test("D2d staging opt-in: 16 символов и origin видны до Telegram approval, нет auto-login", async ({ page }) => {
    const code = "abcdefghijklmnop";
    const calls: string[] = [];
    await page.route("**/api/subpage/v1/**", async route => {
      calls.push(new URL(route.request().url()).pathname);
      await route.fulfill({
        status: 200, contentType: "application/json",
        headers: { "Cache-Control": "no-store" },
        body: JSON.stringify({ challenge: code, expiresIn: 180 }),
      });
    });
    await page.goto("/");
    const panel = page.getByTestId("d2b-standalone-pilot");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("ВСЕ 16");
    await expect(panel).toContainText("адресной строке");
    await expect(page.getByTestId("d2b-challenge")).toHaveCount(0);
    expect(calls).toEqual([]);
    await panel.getByRole("button", { name: "Создать запрос" }).click();
    await expect(page.getByTestId("d2b-challenge")).toHaveText(code);
    await expect(page.getByTestId("d2d-staging-origin")).toContainText(
      new URL(page.url()).origin);
    await expect(panel.getByTestId("d2b-standalone-summary")).toHaveCount(0);
    expect(calls).toEqual(["/api/subpage/v1/auth/standalone/start"]);
  });
});
