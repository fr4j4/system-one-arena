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
  await page.getByLabel("Avance de turnos").selectOption("step");
  await expect(page.getByLabel("Presupuesto en milisegundos")).toHaveCount(0);
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
  await expect(page.locator(".case-table tbody tr")).toHaveCount(25);
  await page.screenshot({
    path: "/tmp/arena-dataset-results.png",
    fullPage: true,
  });
  await page
    .locator(".case-table tbody tr")
    .first()
    .getByRole("button")
    .click();
  await expect(
    page.getByRole("region", { name: "Detalle del caso" }),
  ).toBeVisible();
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

test("scenario controls follow turns, realtime and datasets", async ({
  page,
}) => {
  await expect(page.getByLabel("Velocidad del juego")).toBeVisible();
  await expect(page.getByLabel("Presupuesto en milisegundos")).toHaveCount(0);
  await page
    .getByLabel("Experiencia", { exact: true })
    .selectOption("evaluate");
  await expect(page.getByLabel("Velocidad del juego")).toBeDisabled();
  await expect(page.getByLabel("Velocidad del juego")).toHaveValue("1");
  await page.getByRole("button", { name: /Tic-tac-toe/ }).click();
  await expect(page.getByLabel("Avance de turnos")).toBeVisible();
  await expect(page.getByLabel("Velocidad del juego")).toHaveCount(0);
  await page.getByRole("button", { name: /Decisiones 9/ }).click();
  await page.getByRole("button", { name: /Tickets de soporte/ }).click();
  await expect(page.getByLabel("Tamaño de muestra")).toBeVisible();
  await expect(page.getByText(/25 de 240 casos disponibles/)).toBeVisible();
  await page.getByLabel("Tamaño de muestra").selectOption("500");
  await expect(page.getByText(/240 de 240 casos disponibles/)).toBeVisible();
  await expect(page.getByLabel("Avance de turnos")).toHaveCount(0);
});

test("dataset A/B aligns cases and table pagination preserves all results", async ({
  page,
}) => {
  await page.getByRole("button", { name: /Decisiones 9/ }).click();
  await page.getByRole("button", { name: /Tickets de soporte/ }).click();
  await page.getByLabel("Proveedor", { exact: true }).selectOption("reference");
  await page.getByLabel("Tamaño de muestra").selectOption("100");
  await page.getByRole("button", { name: "Avanzado", exact: true }).click();
  await page.getByLabel("Comparar en vivo").selectOption("random");
  await page.getByRole("button", { name: "Iniciar ejecución" }).click();
  await expect(page.locator(".run-panel .status").first()).toHaveText(
    "Completado",
    { timeout: 25000 },
  );
  await expect(page.locator(".run-panel .status").last()).toHaveText(
    "Completado",
    { timeout: 25000 },
  );
  const panel = page.locator(".run-panel").first();
  await expect(panel.getByText("100 / 100 procesados")).toBeVisible();
  await expect(panel.locator(".case-table tbody tr")).toHaveCount(25);
  await panel.getByRole("button", { name: "Siguiente", exact: true }).click();
  await expect(panel.getByText(/Página 2 de 4/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Comparación por caso" }),
  ).toBeVisible();
  await expect(page.locator(".comparison-table")).not.toContainText(
    "Pendiente",
  );
  await page.getByLabel(/Solo desacuerdos/).check();
  await expect(
    page.locator(".comparison-table tbody tr").first(),
  ).toContainText("Desacuerdo");
});

test("CSV import preserves text, labels and unlabeled cases", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Datasets", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "cases.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      'id,text,expected.department\ncustom-1,"Necesito una factura, por favor",billing\ncustom-2,"Consulta sin etiqueta",\n',
    ),
  });
  await expect(
    page.getByText("Archivo importado.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Guardar y usar" }).click();
  await expect(
    page.getByText("Dataset guardado y seleccionado", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Arena", exact: true }).click();
  await page.getByRole("button", { name: /Decisiones 9/ }).click();
  await page.getByRole("button", { name: /Tickets de soporte/ }).click();
  await page.getByLabel("Proveedor", { exact: true }).selectOption("reference");
  await expect(page.getByText(/2 de 2 casos disponibles/)).toBeVisible();
  await page.getByRole("button", { name: "Iniciar ejecución" }).click();
  await expect(page.locator(".run-panel .status")).toHaveText("Completado");
  await expect(page.locator(".case-table tbody tr")).toHaveCount(2);
  await page.getByLabel("Filtrar evaluación").selectOption("unlabeled");
  await expect(page.locator(".case-table tbody tr")).toHaveCount(1);
  await expect(page.locator(".case-table tbody tr")).toContainText("custom-2");
});

test("every business dataset has 240 cases and expanded moderation runs", async ({
  page,
  request,
}) => {
  for (const name of [
    "tickets",
    "email",
    "spam",
    "moderation",
    "events",
    "hierarchy",
    "incidents",
    "routing",
    "workflow",
  ]) {
    const response = await request.get("/api/fixtures/" + name);
    expect(response.ok()).toBeTruthy();
    const items = await response.json();
    expect(items).toHaveLength(240);
    expect(new Set(items.map((r: any) => r.id)).size).toBe(240);
  }
  await page.getByRole("button", { name: /Decisiones 9/ }).click();
  await page.getByRole("button", { name: /Moderación/ }).click();
  await expect(page.getByText(/25 de 240 casos disponibles/)).toBeVisible();
  await page.getByLabel("Tamaño de muestra").selectOption("100");
  await page.getByLabel("Proveedor", { exact: true }).selectOption("reference");
  await page.getByRole("button", { name: "Iniciar ejecución" }).click();
  await expect(page.locator(".run-panel .status")).toHaveText("Completado");
  await expect(page.getByText("100 / 100 procesados")).toBeVisible();
});

test("3D fighting shares a battle with independent model slots", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.getByRole("button", { name: /Fighting/ }).click();
  await page.getByLabel("Modelo Player 1").selectOption("reference");
  await page.getByLabel("Modelo Player 2").selectOption("random");
  await page.getByLabel("Formato de batalla").selectOption("1");
  await page.getByLabel("Tiempo por ronda").selectOption("15");
  await expect(page.locator('canvas[data-renderer="threejs"]')).toBeVisible();
  await page.getByRole("button", { name: "Iniciar ejecución" }).click();
  const panel = page.locator(".fighting-run");
  await expect(panel.locator(".status")).toHaveText("En vivo");
  await expect(panel.locator('canvas[data-renderer="threejs"]')).toBeVisible();
  await expect(panel.locator(".fighter-models button").nth(0)).toContainText(
    "REFERENCE",
  );
  await expect(panel.locator(".fighter-models button").nth(1)).toContainText(
    "RANDOM",
  );
  await expect(
    panel.locator(".fighter-models button").nth(0),
  ).not.toContainText("0 acciones aplicadas");
  await expect(
    panel.locator(".fighter-models button").nth(1),
  ).not.toContainText("0 acciones aplicadas");
  await panel.locator(".fighter-models button").nth(1).click();
  await page.getByRole("button", { name: "Entrada", exact: true }).click();
  await expect(panel.locator("pre")).toContainText('"player_id": "p2"');
  await page.screenshot({ path: "/tmp/arena-fighting.png", fullPage: true });
  await panel.getByRole("button", { name: "Detener", exact: true }).click();
  await expect(panel.locator(".status")).toHaveText("Detenido");
  const runs = await (await request.get("/api/runs")).json();
  const battle = runs.find(
    (r: any) => r.config.scenario === "fighting" && r.status === "stopped",
  );
  expect(battle.players.p1.counts.applied).toBeGreaterThan(0);
  expect(battle.players.p2.counts.applied).toBeGreaterThan(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "/tmp/arena-fighting-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
