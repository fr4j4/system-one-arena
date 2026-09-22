import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page, request }) => {
  const runs = await (await request.get("/api/runs")).json();
  for (const r of runs.filter((r: any) =>
    ["running", "paused", "preparing"].includes(r.status),
  ))
    await request.post(`/api/runs/${r.id}/control`, {
      data: { command: "stop" },
    });
  await page.goto("/");
  await expect(page.getByText("Backend conectado")).toBeVisible();
});

test("desktop preview, live Snake, metrics and timeline", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await expect(
    page.getByRole("heading", { name: "La inteligencia, en acción." }),
  ).toBeVisible();
  await expect(page.locator(".scenario-card")).toHaveCount(6);
  await page.screenshot({ path: "/tmp/arena-desktop.png", fullPage: true });
  await page.getByRole("button", { name: "Iniciar ejecución" }).click();
  await expect(page.locator(".run-panel .status")).toHaveText(
    /En vivo|Completado/,
    { timeout: 15000 },
  );
  await expect(
    page.locator(".run-panel .metric").first().locator("strong"),
  ).not.toContainText("—", { timeout: 10000 });
  await page.getByRole("button", { name: "Timeline", exact: true }).click();
  await expect(page.locator(".timeline-row.applied").first()).toBeVisible();
  await page.screenshot({ path: "/tmp/arena-live.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("step mode tic-tac-toe only acts on demand", async ({ page }) => {
  await page.getByRole("button", { name: /Tic-tac-toe/ }).click();
  await page.getByLabel("Proveedor", { exact: true }).selectOption("reference");
  await page.getByLabel("Reloj").selectOption("step");
  await page.getByLabel("Presupuesto en milisegundos").fill("2000");
  await page.getByRole("button", { name: "Iniciar ejecución" }).click();
  await expect(page.locator(".run-panel .status")).toHaveText("En vivo");
  await expect(page.getByText("Las probabilidades aparecerán")).toBeVisible();
  await page.getByRole("button", { name: "Una decisión" }).click();
  await expect(page.locator(".distribution")).toBeVisible();
  const stop = page
    .locator(".run-header")
    .getByRole("button", { name: "Detener", exact: true });
  await expect(stop).toHaveText("Detener");
  await stop.click();
  await expect(page.locator(".run-panel .status")).toHaveText("Detenido");
  await expect(stop).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Una decisión" }),
  ).toBeDisabled();
});

test("ticket classification and replay", async ({ page }) => {
  await page.getByRole("button", { name: /Decisiones 9/ }).click();
  await page.getByRole("button", { name: /Tickets de soporte/ }).click();
  await page.getByLabel("Proveedor", { exact: true }).selectOption("reference");
  await page.getByRole("button", { name: "Iniciar ejecución" }).click();
  await expect(page.locator(".run-panel .status")).toHaveText("Completado", {
    timeout: 10000,
  });
  await expect(page.locator(".document-results>div")).toHaveCount(4);
  await page.getByRole("button", { name: "Historial", exact: true }).click();
  await page.locator(".history-list button").first().click();
  await expect(page.locator(".replay-controls")).toBeVisible();
  await page.getByRole("button", { name: "Reproducir replay" }).click();
});

test("workflow templates, validation, and dataset editor", async ({ page }) => {
  await page.getByRole("button", { name: "Árboles", exact: true }).click();
  await expect(page.locator(".flow-node")).toHaveCount(5);
  await page.getByRole("button", { name: "Validar", exact: true }).click();
  await expect(page.getByText("Árbol válido:")).toBeVisible();
  await page.getByLabel("Plantilla de árbol").selectOption("email");
  await expect(page.locator(".flow-node")).toHaveCount(4);
  await page.screenshot({ path: "/tmp/arena-workflow.png", fullPage: true });
  await page.getByRole("button", { name: "Datasets", exact: true }).click();
  await expect(page.getByLabel("Editor JSONL")).toContainText("");
  await page.getByRole("button", { name: "Guardar y usar" }).click();
  await expect(page.getByText("Dataset guardado y seleccionado")).toBeVisible();
});

test("paired benchmark presents observed metrics", async ({ page }) => {
  await page.getByRole("button", { name: "Experimentos", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Escenario", exact: true })
    .selectOption("tickets");
  await page.getByLabel("Mediciones", { exact: true }).fill("4");
  await page.getByLabel("Calentamiento", { exact: true }).fill("1");
  await page.getByRole("button", { name: "Iniciar benchmark" }).click();
  await expect(
    page.getByText("Evaluación completada", { exact: true }),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.locator(".result-card")).toHaveCount(2);
  await page.screenshot({ path: "/tmp/arena-benchmark.png", fullPage: true });
});

test("mobile layout does not overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "/tmp/arena-mobile.png", fullPage: true });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(
    page.getByRole("button", { name: "Iniciar ejecución" }),
  ).toBeVisible();
});
