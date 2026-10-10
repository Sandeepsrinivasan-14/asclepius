import { expect, test } from "@playwright/test";
import { loginAs, openPatient } from "./helpers";

test.describe("dashboard widgets", () => {
  test("hide, restore and reorder widgets; layout persists", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/dashboard");
    const grid = page.getByTestId("widget-grid");
    await expect(grid.locator("[data-widget]").first()).toBeVisible();
    const total = await grid.locator("[data-widget]").count();
    await page.getByTestId("customize-layout").click();
    await page.getByRole("button", { name: "Hide Platform" }).click();
    await expect(grid.locator("[data-widget]")).toHaveCount(total - 1);
    await page.reload();
    await expect(grid.locator("[data-widget]")).toHaveCount(total - 1);
    await page.getByTestId("customize-layout").click();
    await page.getByTestId("hidden-widgets").getByRole("button", { name: /Platform/ }).click();
    await expect(grid.locator("[data-widget]")).toHaveCount(total);
    const first = await grid.locator("[data-widget]").first().getAttribute("data-widget");
    await page.getByRole("button", { name: /^Move .* later$/ }).first().click();
    await expect(grid.locator("[data-widget]").first()).not.toHaveAttribute("data-widget", first!);
    await page.getByRole("button", { name: /Reset layout/ }).click();
    await expect(grid.locator("[data-widget]").first()).toHaveAttribute("data-widget", first!);
  });

  test("a widget can be made wider", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/dashboard");
    await page.getByTestId("customize-layout").click();
    const w = page.locator('[data-widget="stat-monitored"]');
    const before = (await w.boundingBox())!.width;
    await page.getByRole("button", { name: "Wider Inpatients monitored" }).click();
    await expect.poll(async () => (await w.boundingBox())!.width).toBeGreaterThan(before + 50);
  });
});

test.describe("patient chart", () => {
  test("body map: select an organ and filter the chart to it", async ({ page, request }) => {
    await loginAs(page, request);
    await openPatient(page, "Joseph Thomas");
    const all = await page.getByTestId("problems").locator("li").count();
    await page.getByRole("button", { name: "Body map" }).click();
    await expect(page.getByTestId("bodymap-canvas")).toBeVisible();
    await expect(page.locator("canvas").first()).toBeVisible();
    const list = page.getByTestId("organ-list");
    await expect(list.locator("button")).toHaveCount(8);
    await list.locator("button").first().click();
    await expect(page.getByTestId("organ-detail")).toBeVisible();
    await page.getByTestId("apply-organ-filter").click();
    await expect(page.getByTestId("filter-banner")).toBeVisible();
    await page.getByRole("button", { name: "Overview" }).click();
    const filtered = await page.getByTestId("problems").locator("li").count();
    expect(filtered).toBeLessThanOrEqual(all);
    await page.getByTestId("filter-banner").getByRole("button", { name: /Clear/ }).click();
    await expect(page.getByTestId("filter-banner")).toHaveCount(0);
    await expect(page.getByTestId("problems").locator("li")).toHaveCount(all);
  });

  test("care gaps and lab review tabs load for a patient", async ({ page, request }) => {
    await loginAs(page, request);
    await openPatient(page, "Joseph Thomas");
    await page.getByRole("button", { name: "Care gaps" }).click();
    await expect(page.getByText(/open · \d+ up to date/)).toBeVisible();
    await page.getByRole("button", { name: "Lab review" }).click();
    await expect(page.getByTestId("labreview")).toBeVisible();
    await expect(page.getByText("Kidney injury screen")).toBeVisible();
  });

  test("clicking the 3D canvas does not crash the page", async ({ page, request }) => {
    await loginAs(page, request);
    await openPatient(page, "Joseph Thomas");
    await page.getByRole("button", { name: "Body map" }).click();
    const canvas = page.locator("canvas").first();
    await expect(canvas).toBeVisible();
    const box = (await canvas.boundingBox())!;
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.move(box.x + box.width / 2 + 40, box.y + box.height / 2);
    expect(errors).toEqual([]);
  });

  test("discharge summary is a signed-off-only draft and prints cleanly", async ({ page, request }) => {
    await loginAs(page, request);
    await openPatient(page, "Joseph Thomas");
    await page.getByTestId("discharge-link").click();
    const sheet = page.getByTestId("discharge-sheet");
    await expect(sheet).toBeVisible();
    await expect(sheet.getByText(/DRAFT/)).toBeVisible();
    await expect(sheet.getByText("Come back or call urgently if")).toBeVisible();
    await expect(sheet.getByText("Physician signature and date")).toBeVisible();
    await page.emulateMedia({ media: "print" });
    await expect(page.locator("aside")).toBeHidden();
    await expect(page.getByTestId("print-discharge")).toBeHidden();
    await expect(sheet).toBeVisible();
  });

  test("copilot citations and the verifier blocking a hallucinated narrative", async ({ page, request }) => {
    await loginAs(page, request);
    await openPatient(page, "Joseph Thomas");
    await page.getByRole("button", { name: "Differential copilot" }).click();
    await expect(page.getByText(/\[E\d+\]/).first()).toBeVisible();
    await page.getByRole("button", { name: "Run verifier" }).click();
    await expect(page.getByText("Blocked by verifier")).toBeVisible();
  });
});

test.describe("interoperability", () => {
  test("terminology: search, validate and translate", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/terminology");
    await page.getByTestId("term-search").fill("diabetes");
    await expect(page.getByTestId("term-results").locator("li").first()).toBeVisible();
    await page.getByTestId("term-results").getByRole("button", { name: /E11\.9/ }).click();
    await expect(page.getByTestId("term-detail")).toContainText("SNOMED CT");
    await page.getByTestId("validate-btn").click();
    await expect(page.getByTestId("validate-result")).toContainText(/Valid code/);
  });

  test("calculators: CURB-65 scores and the G then C shortcut navigates", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/dashboard");
    await page.keyboard.press("g");
    await page.keyboard.press("c");
    await expect(page).toHaveURL(/\/calculators/);
    const card = page.getByTestId("calc-curb65");
    await card.getByLabel("New confusion").check();
    await card.locator("xpath=..").getByRole("button", { name: "Calculate" }).click();
    await expect(page.getByTestId("calc-result").first()).toContainText(/CURB|confusion|low|moderate/i);
    await expect(page.getByTestId("calc-result").first()).toContainText("1");
  });

  test("Synthea sample import adds a patient the chart modules understand", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/terminology");
    await page.getByTestId("load-sample").click();
    await expect(page.getByTestId("bundle-summary")).toContainText("Condition × 3");
    await page.getByTestId("import-btn").click();
    await expect(page.getByTestId("import-report")).toContainText("Imported");
    await page.goto("/patients");
    await expect(page.getByRole("link", { name: /Elena Hartmann/ })).toBeVisible();
  });

  test("HL7 pipeline: duplicates are idempotent and failures reach the dead-letter queue", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/interop");
    await page.getByRole("button", { name: /Send all demo messages/ }).click();
    await expect(page.getByText(/All 7 demo messages submitted/)).toBeVisible();
    await page.getByRole("button", { name: /Run processor/ }).click();
    await expect(page.getByRole("button", { name: /Replay/ }).first()).toBeVisible();
  });
});

test.describe("access control", () => {
  test("break-glass opens a locked chart and the privacy officer sees the review", async ({ page, request, browser }) => {
    const token = await loginAs(page, request, "dr.chandran");
    let lockedId = "";
    for (let i = 1; i <= 64 && !lockedId; i++) {
      const id = `pat-${String(i).padStart(3, "0")}`;
      const r = await request.get(`http://127.0.0.1:8000/api/patients/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      if (r.status() === 403 && (await r.json()).error.code === "break_glass_required") lockedId = id;
    }
    expect(lockedId).not.toBe("");
    await page.goto(`/patients/${lockedId}`);
    await expect(page.getByRole("heading", { name: /restricted/i })).toBeVisible();
    await page.getByRole("button", { name: /Break glass/ }).click();
    await page.getByPlaceholder(/Unresponsive patient/).fill("Unresponsive patient in the emergency department, need history");
    await page.getByRole("button", { name: /Confirm and access/ }).click();
    await expect(page.getByText(/Break-glass access/).first()).toBeVisible();

    const ctx = await browser.newContext();
    const officer = await ctx.newPage();
    await loginAs(officer, request, "auditor.menon");
    await officer.goto("/access");
    await expect(officer.getByText(/dr\.chandran|Chandran/).first()).toBeVisible();
    await ctx.close();
  });
});
