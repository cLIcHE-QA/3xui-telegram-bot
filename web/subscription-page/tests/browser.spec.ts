import { test, expect } from "@playwright/test";

test("четыре варианта подписки и инструкции доступны без реальных действий", async ({ page }) => {
  const unexpected: string[] = [];
  page.on("request", (req) => {
    if (new URL(req.url()).origin !== "http://127.0.0.1:4173") unexpected.push(req.url());
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Безопасный интернет. Без лишних сложностей." })).toBeVisible();
  await expect(page.locator(".portal-logo img")).toHaveAttribute("src", "/brand/raccoon-wrench.svg");
  await expect(page.locator(".hero-art img")).toBeVisible();
  await expect(page.getByRole("button", { name: "Получить ссылку" })).toBeDisabled();
  const control = page.getByTestId("subscription-layout");
  const preview = page.getByTestId("subscription-preview");
  for (const mode of ["expanded", "cards", "collapsed", "hidden"]) {
    await control.getByText(mode, { exact: true }).click();
    await expect(preview).toHaveAttribute("data-mode", mode);
  }
  await control.getByText("cards", { exact: true }).click();
  await expect(preview.locator(".subscription-info-grid .mantine-Card-root")).toHaveCount(3);
  const scenarios = page.getByTestId("subscription-scenario");
  await control.getByText("expanded", { exact: true }).click();
  for (const [state,label] of [["unknown","Нет данных"],["active","Активна · пример"],["expired","Истекла · пример"],["pending","Ожидает · пример"]]) {
    await scenarios.getByText(label, { exact: true }).click();
    await expect(preview).toHaveAttribute("data-scenario", state);
    await expect(preview.getByText("ДЕМО")).toBeVisible();
    await expect(preview.getByText("Вымышленные данные, не ваша подписка")).toBeVisible();
    await expect(preview.getByRole("button", { name: "Получить ссылку" })).toBeDisabled();
  }
  await control.getByText("hidden", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Получить ссылку" })).toHaveCount(0);

  const guides = page.getByTestId("guides-layout");
  for (const mode of ["timeline", "minimal", "accordion", "cards"]) {
    await guides.getByText(mode, { exact: true }).click();
    await expect(page.getByText("Установить приложение").first()).toBeVisible();
  }
  expect(unexpected).toEqual([]);
});

test("RTL, клавиатура и мобильная компоновка без горизонтального переполнения", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const language = page.getByRole("combobox", { name: "Language" });
  await language.click();
  await page.getByRole("option", { name: "FA" }).click();
  await expect(page.locator("[dir=rtl]").first()).toBeVisible();
  await page.keyboard.press("Tab");
  const focused = await page.evaluate(() => document.activeElement?.tagName.toLowerCase());
  expect(["button", "input", "a"]).toContain(focused);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await expect(page.getByRole("heading", { name: "اینترنت امن‌تر. بدون پیچیدگی." })).toBeVisible();
  await expect(page.locator(".hero")).toBeVisible();
});

test("five locales preserve preview safety and allow navigation", async ({ page }) => {
  await page.goto("/");
  const language = page.getByRole("combobox", { name: "Language" });
  for (const locale of ["EN", "FR", "ZH", "FA", "RU"]) {
    await language.click();
    await page.getByRole("option", { name: locale }).click();
    await expect(page.getByTestId("subscription-scenario")).toBeVisible();
    const linkName: Record<string,string> = { EN:"Get Link",FR:"Obtenir le lien",ZH:"获取链接",FA:"دریافت پیوند",RU:"Получить ссылку" };
    await expect(page.getByRole("button", { name: linkName[locale] })).toBeDisabled();
    await expect(page.locator("html")).toHaveAttribute("lang", locale.toLowerCase());
  }
});

test("выбор клиента использует нейтральную иконку и не вызывает внешних запросов", async ({ page }) => {
  const external: string[] = [];
  page.on("request", request => {
    if (new URL(request.url()).origin !== "http://127.0.0.1:4173") external.push(request.url());
  });
  await page.goto("/");
  const chooser = page.getByTestId("client-choice");
  await expect(chooser).toHaveCount(1);
  await expect(chooser.first()).toHaveAttribute("aria-pressed", "true");
  await expect(chooser.first().locator(".client-icon svg")).toBeVisible();
  await page.getByRole("tab", { name: "Android" }).click();
  await expect(page.getByText("Для этой платформы нет настроенных клиентов.").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Получить ссылку" })).toBeDisabled();
  expect(external).toEqual([]);
});
