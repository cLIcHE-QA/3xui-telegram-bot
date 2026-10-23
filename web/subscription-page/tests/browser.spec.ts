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
    await control.locator(`button[data-value="${mode}"]`).click();
    await expect(preview).toHaveAttribute("data-mode", mode);
  }
  await control.locator('button[data-value="cards"]').click();
  await expect(preview.locator(".subscription-info-grid .mantine-Card-root")).toHaveCount(4);
  const scenarios = page.getByTestId("subscription-scenario");
  await control.locator('button[data-value="expanded"]').click();
  for (const [state,label] of [["unknown","Нет данных"],["active","Активна · пример"],["expired","Истекла · пример"],["pending","Ожидает · пример"]]) {
    await scenarios.locator(`button[data-value="${state}"]`).click();
    await expect(preview).toHaveAttribute("data-scenario", state);
    await expect(preview.getByText("ДЕМО")).toBeVisible();
    await expect(preview.getByText("Вымышленные данные, не ваша подписка")).toBeVisible();
    await expect(preview.getByRole("button", { name: "Получить ссылку" })).toBeDisabled();
  }
  await control.locator('button[data-value="hidden"]').click();
  await expect(page.getByRole("button", { name: "Получить ссылку" })).toHaveCount(0);

  const guides = page.getByTestId("guides-layout");
  for (const mode of ["timeline", "minimal", "accordion", "cards"]) {
    await guides.locator(`button[data-value="${mode}"]`).click();
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

test("full-page visual evidence for four instruction layouts and empty state", async ({ page }, testInfo) => {
  await page.goto("/");
  const guides = page.getByTestId("guides-layout");
  const full = async (label: string) => {
    const path = testInfo.outputPath(label + ".png");
    await page.screenshot({ path, fullPage: true, animations: "disabled" });
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    expect(height).toBeGreaterThan(testInfo.project.use.viewport?.height ?? 700);
  };
  for (const mode of ["cards", "timeline", "accordion", "minimal"]) {
    await guides.locator(`button[data-value="${mode}"]`).click();
    const preview = page.getByTestId("guide-preview");
    await expect(preview).toHaveAttribute("data-mode", mode);
    await expect(preview.getByText("Установить приложение").first()).toBeVisible();
    await expect(preview.getByText("Предпросмотр: ссылки, установка и импорт подписки отключены.")).toBeVisible();
    await full("guide-" + mode + "-" + testInfo.project.name);
  }
  await page.getByRole("tab", { name: "Android" }).click();
  await expect(page.getByTestId("guide-preview")).toContainText("Инструкции пока не настроены");
  await full("guide-empty-" + testInfo.project.name);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test("visual preview of four synthetic statuses does not unlock actions", async ({ page }, testInfo) => {
  await page.goto("/");
  const picker=page.getByTestId("subscription-scenario");
  const preview=page.getByTestId("subscription-preview");
  for(const [state,label] of [["unknown","Нет данных"],["active","Активна · пример"],["expired","Истекла · пример"],["pending","Ожидает · пример"]]){
    await picker.locator(`button[data-value="${state}"]`).click();
    await expect(preview).toHaveAttribute("data-scenario",state);
    await expect(preview.getByRole("button",{name:"Получить ссылку"})).toBeDisabled();
    await page.screenshot({path:testInfo.outputPath("subscription-"+state+"-"+testInfo.project.name+".png"),fullPage:true,animations:"disabled"});
  }
});

test("320/390/430/768/1024px readable touch targets, five locales and keyboard", async ({page}, testInfo) => {
  test.setTimeout(90000);
  await page.goto("/");
  for(const width of [320,390,430,768,1024]){
    await page.setViewportSize({width,height:844});
    for(const locale of (width===320||width===390?["RU","EN","FR","ZH","FA"]:["RU","FA"])){
      const lang=page.getByRole("combobox",{name:"Language"});
      await lang.click();
      await page.getByRole("option",{name:locale}).click();
      const measurements=await page.evaluate(() => [...document.querySelectorAll(".preview-mode-button")].map(e=>{
        const rect=e.getBoundingClientRect(); return {h:rect.height,w:rect.width,left:rect.left,right:rect.right,font:parseFloat(getComputedStyle(e).fontSize)};
      }));
      expect(measurements).toHaveLength(13);
      for(const m of measurements){
        expect(m.h).toBeGreaterThanOrEqual(44);
        expect(m.font).toBeGreaterThanOrEqual(13);
        expect(m.left).toBeGreaterThanOrEqual(-1);
        expect(m.right).toBeLessThanOrEqual(width+1);
      }
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
      if(width===320&&locale==="FA")await page.screenshot({path:testInfo.outputPath("touch-320-fa.png"),fullPage:true});
    }
  }
  await page.setViewportSize({width:320,height:700});
  const lang=page.getByRole("combobox",{name:"Language"});
  await lang.click();await page.getByRole("option",{name:"RU"}).click();
  const hidden=page.getByTestId("subscription-layout").locator('button[data-value="hidden"]');
  await hidden.focus();await page.keyboard.press("Enter");
  await expect(hidden).toHaveAttribute("aria-pressed","true");
  const cards=page.getByTestId("subscription-layout").locator('button[data-value="cards"]');
  await cards.focus();await page.keyboard.press("Space");
  await expect(cards).toHaveAttribute("aria-pressed","true");
});

test("карусель: навигация, один шаг и сброс при смене ОС", async ({page}, testInfo) => {
  await page.goto("/");
  const carousel=page.getByTestId("guide-carousel");
  await expect(page.getByTestId("guide-preview")).toHaveAttribute("data-mode","carousel");
  await expect(carousel).toBeVisible();
  await expect(carousel.getByText("Установить приложение")).toBeVisible();
  await expect(carousel.getByText("Добавить подписку")).toHaveCount(0);
  await expect(page.getByTestId("guide-previous")).toBeDisabled();
  await page.getByTestId("guide-next").click();
  await expect(carousel.getByText("Добавить подписку")).toBeVisible();
  await expect(carousel.getByText("Установить приложение")).toHaveCount(0);
  await expect(page.getByTestId("guide-next")).toBeDisabled();
  await carousel.locator("button").first().focus();
  await page.keyboard.press("Enter");
  await expect(carousel.getByText("Установить приложение")).toBeVisible();
  await page.getByRole("tab",{name:"Android"}).click();
  await expect(page.getByTestId("guide-preview")).toContainText("Инструкции пока не настроены");
  await page.getByRole("tab",{name:"iOS"}).click();
  await expect(page.getByTestId("guide-previous")).toBeDisabled();
  const css=await page.locator(".device-tabs").evaluate(el=>{
    const list=getComputedStyle(el),tab=getComputedStyle(el.querySelector('[role="tab"]')!),parent=getComputedStyle(el.closest(".platform-segment")!);
    return {outline:list.borderTopWidth,tabBottom:tab.borderBottomWidth,divider:parent.borderBottomWidth};
  });
  expect(parseFloat(css.outline)).toBeGreaterThan(0);
  expect(parseFloat(css.tabBottom)).toBe(0);
  expect(parseFloat(css.divider)).toBe(0);
  await page.setViewportSize({width:320,height:700});
  await expect(page.locator(".device-tabs")).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:testInfo.outputPath("compact-guide-320.png"),fullPage:true});
});

test("карусель — только UI, старые режимы доступны", async ({page})=>{
  await page.goto("/");
  const picker=page.getByTestId("guides-layout");
  await expect(picker.locator("button")).toHaveCount(5);
  await picker.locator('button[data-value="cards"]').click();
  await expect(page.getByTestId("guide-preview")).toHaveAttribute("data-mode","cards");
  await picker.locator('button[data-value="carousel"]').click();
  await expect(page.getByTestId("guide-preview")).toHaveAttribute("data-mode","carousel");
});

test("смысловые плитки подписки: план неизвестен, трафик/срок — только синтетические",async({page},testInfo)=>{
 await page.goto("/");
 const v=page.getByTestId("subscription-preview");
 const sc=page.getByTestId("subscription-scenario");
 for(const state of ["unknown","active","expired","pending"]){
   await sc.locator('button[data-value="'+state+'"]').click();
   await expect(v).toHaveAttribute("data-scenario",state);
   for(const key of ["plan","status","traffic","expiry"])await expect(v.getByTestId("subscription-tile-"+key)).toBeVisible();
   await expect(v.getByTestId("subscription-tile-plan")).toContainText("Не указан");
   await expect(v.locator(".subscription-reset")).toContainText("Нет данных");
   await expect(v.getByRole("button",{name:"Получить ссылку"})).toBeDisabled();
   if(state==="active"){await expect(v.getByTestId("subscription-tile-traffic")).toContainText("24.6 / 100 GB");}
   if(state==="unknown"){await expect(v.getByTestId("subscription-tile-traffic")).toContainText("Нет данных");}
   await page.screenshot({path:testInfo.outputPath("subscription-theme-"+state+".png"),fullPage:true,animations:"disabled"});
 }
 await page.getByTestId("subscription-layout").locator('button[data-value="cards"]').click();
 await expect(v.locator(".subscription-info-grid .mantine-Card-root")).toHaveCount(4);
});
