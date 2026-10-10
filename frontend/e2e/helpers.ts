import { expect, type APIRequestContext, type Page } from "@playwright/test";

const API = "http://127.0.0.1:8000";

/** Sign in through the API and hand the token to the page, skipping the tour unless asked. */
export async function loginAs(page: Page, request: APIRequest, username = "dr.rao", opts: { tour?: boolean } = {}) {
  const r = await request.post(`${API}/api/auth/login`, { data: { username } });
  expect(r.ok()).toBeTruthy();
  const { token } = await r.json();
  await page.addInitScript(([t, tour]) => {
    sessionStorage.setItem("asc.token", t as string);
    if (!tour) localStorage.setItem("asc.tour.v1", "done");
  }, [token, !!opts.tour] as const);
  return token as string;
}
type APIRequest = APIRequestContext;

export async function openPatient(page: Page, name: string) {
  await page.goto("/patients");
  await page.getByRole("link", { name: new RegExp(name) }).first().click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
}
