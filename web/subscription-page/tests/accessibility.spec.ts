import { test, expect } from "@playwright/test";

const BASE = "http://127.0.0.1:4173";

async function noHorizontalOverflow(page: import("@playwright/test").Page) {
  return page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
}

test("200% текст: отсутствие обрезки, RTL и доступные действия", async ({ page }, testInfo) => {
  test.setTimeout(90000);
  await page.goto("/");
  const targets = [".hero h1", ".hero p", ".guide-description", ".preview-mode-button", ".client-copy strong"];
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 812 });
    for (const language of ["RU", "FA"]) {
      const select = page.getByRole("combobox", { name: "Language" });
      await select.click();
      await page.getByRole("option", { name: language }).click();
      const before = await page.evaluate((selectors) => selectors.map((sel) => parseFloat(getComputedStyle(document.querySelector(sel)!).fontSize)), targets);
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      const after = await page.evaluate((selectors) => selectors.map((sel) => parseFloat(getComputedStyle(document.querySelector(sel)!).fontSize)), targets);
      for (let i = 0; i < targets.length; i++) {
        expect(after[i], targets[i] + " 200%").toBeGreaterThanOrEqual(before[i] * 1.75);
      }
      const noOverflow = await noHorizontalOverflow(page);
      if (!noOverflow) {
        const offenders = await page.evaluate(() => ({
          innerWidth, viewport: document.documentElement.clientWidth,
          rootScroll: document.documentElement.scrollWidth, bodyScroll: document.body.scrollWidth,
          elements: [...document.querySelectorAll("*")].map(node => {
            const r = node.getBoundingClientRect();
            const style = getComputedStyle(node);
            return { tag: node.tagName, className: typeof node.className === "string" ? node.className.slice(0, 90) : "",
              text: (node.textContent || "").trim().slice(0, 50),
              left: Math.round(r.left), right: Math.round(r.right), scroll: (node as HTMLElement).scrollWidth,
              client: (node as HTMLElement).clientWidth, overflowX: style.overflowX };
          }).filter(x => x.right > innerWidth + 2 && x.left < innerWidth + 2).slice(0, 35)
        }));
        console.log("D1A_TEXT_ZOOM_OVERFLOW", JSON.stringify({ width, language, offenders }));
      }
      expect(noOverflow, "width " + width + ", language " + language).toBe(true);
      await expect(page.getByTestId("subscription-scenario").locator('button[data-value="active"]')).toBeVisible();
      await page.getByTestId("subscription-scenario").locator('button[data-value="active"]').click();
      await expect(page.getByTestId("subscription-preview")).toHaveAttribute("data-scenario", "active");
      if (width === 320 && language === "FA") {
        await page.screenshot({ path: testInfo.outputPath("text-zoom-200-fa-320.png"), fullPage: true, animations: "disabled" });
      }
      await page.evaluate(() => { document.documentElement.style.fontSize = ""; });
    }
  }
});

function luminance(rgb: string) {
  const parts = rgb.match(/[\d.]+/g)?.slice(0, 3).map(Number);
  if (!parts || parts.length !== 3) throw new Error("Expected rgb(): " + rgb);
  const [r, g, b] = parts.map((n) => {
    const v = n / 255;
    return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

test("основные текстовые цвета: контраст не ниже 4.5:1", async ({ page }) => {
  await page.goto("/");
  const samples = [
    { selector: ".guide-footnote", bg: "rgb(12, 25, 38)" },
    { selector: ".preview-mode-button[data-value='hidden']", bg: "rgb(21, 39, 56)" },
    { selector: ".portal-footer", bg: "rgb(6, 11, 17)" },
    { selector: ".hero p", bg: "rgb(11, 30, 50)" },
  ];
  for (const sample of samples) {
    const foreground = await page.locator(sample.selector).first().evaluate(el => getComputedStyle(el).color);
    const a = luminance(foreground), b = luminance(sample.bg);
    const ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    expect(ratio, sample.selector + " / " + sample.bg).toBeGreaterThanOrEqual(4.5);
  }
});

test("WebView-like: оболочка iOS WebKit без реальных ключей и внешних запросов", async ({ page }, testInfo) => {
  test.setTimeout(60000);
  const external: string[] = [];
  const errors: string[] = [];
  page.on("request", req => {
    if (new URL(req.url()).origin !== BASE) external.push(req.url());
  });
  page.on("pageerror", err => errors.push(err.message));
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator('meta[name="viewport"]')).toHaveAttribute("content", /viewport-fit=cover/);
  await expect(page.locator(".portal-logo img")).toBeVisible();
  await expect(page.getByRole("button", { name: "Получить ссылку" })).toBeDisabled();
  await page.getByTestId("guides-layout").locator('button[data-value="timeline"]').click();
  await expect(page.getByTestId("guide-preview")).toHaveAttribute("data-mode", "timeline");
  const language = page.getByRole("combobox", { name: "Language" });
  await language.click();
  await page.getByRole("option", { name: "FA" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  expect(await noHorizontalOverflow(page)).toBe(true);
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("webview-like-fa-" + testInfo.project.name + ".png"), fullPage: true, animations: "disabled" });
});
