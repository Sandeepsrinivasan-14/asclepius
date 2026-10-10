import { expect, test } from "@playwright/test";
import { loginAs } from "./helpers";

test.describe("sign-in and role-based access", () => {
  test("persona login lands on the command center", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("asc.tour.v1", "done"));
    await page.goto("/login");
    await page.getByRole("button", { name: /Dr\. Meera Rao/ }).click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { name: /Dr\. Meera/ })).toBeVisible();
  });

  test("unauthenticated visits are redirected to login", async ({ page }) => {
    await page.goto("/patients");
    await expect(page).toHaveURL(/\/login/);
  });

  test("a pharmacist sees limited monitoring data", async ({ page, request }) => {
    await loginAs(page, request, "pharm.iyer");
    await page.goto("/dashboard");
    await expect(page.getByText(/not part of your role/i).first()).toBeVisible();
  });
});

test.describe("themes and accessibility", () => {
  test("switching to Clinic day applies and survives a reload", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Appearance" }).click();
    await page.getByRole("menuitemradio", { name: /Clinic day/ }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "day");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "day");
    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(247, 243, 234)");
  });

  test("ICU night theme and the T shortcut cycle themes", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Appearance" }).click();
    await page.getByRole("menuitemradio", { name: /ICU night/ }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "icu");
    await page.keyboard.press("Escape");
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
    await page.keyboard.press("t");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "night");
  });

  test("high contrast toggles with the H key and is remembered", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/dashboard");
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
    await page.keyboard.press("h");
    await expect(page.locator("html")).toHaveAttribute("data-contrast", "high");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-contrast", "high");
    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(0, 0, 0)");
  });

  test("question mark opens the shortcut list and G then P navigates", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/dashboard");
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
    await page.keyboard.press("?");
    await expect(page.getByTestId("shortcuts")).toBeVisible();
    await page.keyboard.press("?");
    await expect(page.getByTestId("shortcuts")).toBeHidden();
    await page.keyboard.press("g");
    await page.keyboard.press("p");
    await expect(page).toHaveURL(/\/patients$/);
  });

  test("command palette finds a patient and runs actions", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/dashboard");
    await page.keyboard.press("Control+k");
    await page.getByPlaceholder(/Jump to a patient/).fill("Joseph");
    await expect(page.getByRole("button", { name: /Joseph Thomas/ })).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/patients\/pat-/);
    await page.keyboard.press("Control+k");
    await page.getByPlaceholder(/Jump to a patient/).fill("shortcuts");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("shortcuts")).toBeVisible();
  });
});

test.describe("product tour and alerts", () => {
  test("the tour starts for new users, can be stepped through and is remembered", async ({ page, request }) => {
    await loginAs(page, request, "dr.rao", { tour: true });
    await page.goto("/dashboard");
    const tour = page.getByTestId("tour");
    await expect(tour).toBeVisible();
    await expect(tour.getByText("Welcome to Asclepius")).toBeVisible();
    await tour.getByRole("button", { name: /Next/ }).click();
    await expect(tour.getByText("Every module, one sidebar")).toBeVisible();
    await page.keyboard.press("ArrowRight");
    await expect(tour.getByText("Jump anywhere")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(tour).toBeHidden();
    await page.reload();
    await page.waitForTimeout(1500);
    await expect(page.getByTestId("tour")).toHaveCount(0);
  });

  test("the tour can be restarted from the header", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Take the tour" }).click();
    await expect(page.getByTestId("tour")).toBeVisible();
  });

  test("the alerts drawer lists high-risk patients for a physician", async ({ page, request }) => {
    await loginAs(page, request);
    await page.goto("/dashboard");
    await expect(page.getByTestId("alert-count")).toBeVisible();
    await page.getByRole("button", { name: /^Alerts/ }).click();
    const drawer = page.getByTestId("alerts-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText(/NEWS2/).first()).toBeVisible();
  });
});
