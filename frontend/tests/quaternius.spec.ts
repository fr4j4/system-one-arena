import { test, expect } from "@playwright/test";

test("animation comparison loads all fighters, scrubs clips, and never calls models", async ({
  page,
}) => {
  const errors: string[] = [],
    api: string[] = [];
  let animationLoads = 0;
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (r.url().includes("/api/")) api.push(r.url());
    if (r.url().includes("/quaternius/animations.json")) animationLoads++;
  });
  await page.goto("/?animation-lab");
  await expect(page.locator("#root")).toHaveAttribute("data-ready", "true");
  await page.getByRole("button", { name: "Pausar", exact: true }).click();
  for (const fighter of ["ember", "flux", "terra", "nyx"]) {
    await page.locator("#character").selectOption(fighter);
    await expect(page.locator("#character")).toBeEnabled();
    await page.getByLabel("Animación").selectOption("light");
    await page.getByLabel("Progreso").fill("0.3");
    await expect(page.getByRole("status")).toContainText("clip de Quaternius");
    await page.getByLabel("Animación").selectOption("ultimate");
    await expect(page.getByRole("status")).toContainText("original conservada");
  }
  await page.waitForTimeout(300);
  expect(await page.getByLabel("Progreso").inputValue()).toBe("0");
  await expect(page.locator("canvas")).toBeVisible();
  expect(errors).toEqual([]);
  expect(api).toEqual([]);
  expect(animationLoads).toBe(1);
});
