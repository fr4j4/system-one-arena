import { test, expect } from "@playwright/test";
test.beforeEach(async ({ page, request }) => {
  const jobs = await (await request.get("/api/v2/series")).json();
  for (const j of jobs)
    if (j.status === "running")
      await request.post(`/api/v2/series/${j.id}/stop`, { data: {} });
  const matches = await (await request.get("/api/v2/matches")).json();
  for (const m of matches)
    if (["preparing", "running", "paused"].includes(m.status))
      await request.post(`/api/v2/matches/${m.id}/control`, {
        data: { command: "stop" },
      });
  await page.addInitScript(() => {
    localStorage.setItem(
      "eclipse-settings-v2",
      JSON.stringify({ quality: "low", master: 0 }),
    );
  });
});
test("independent slots, live decisions, pause, stop and no further calls", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("button", { name: "P1 Terra", exact: true }).click();
  await page.getByRole("button", { name: "P2 Nyx", exact: true }).click();
  await page.getByLabel("Controlador P2").selectOption("aggressive");
  await expect(
    page.getByRole("button", { name: "Iniciar combate", exact: true }),
  ).toBeEnabled({ timeout: 30000 });
  await page
    .getByRole("button", { name: "Iniciar combate", exact: true })
    .click();
  await expect(page.locator(".inspector-metrics")).toContainText(
    "reference (sin IA)",
    { timeout: 15000 },
  );
  const all = await (await request.get("/api/v2/matches")).json();
  const id = all[0].id;
  await page.getByRole("button", { name: "Pausar", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Reanudar", exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(500);
  const before = await (await request.get(`/api/v2/matches/${id}`)).json();
  await page.waitForTimeout(600);
  const after = await (await request.get(`/api/v2/matches/${id}`)).json();
  expect(after.state.tick).toBe(before.state.tick);
  expect(after.players.map((p: any) => p.counts.accepted)).toEqual(
    before.players.map((p: any) => p.counts.accepted),
  );
  await page.getByRole("button", { name: "Reanudar", exact: true }).click();
  await page.waitForTimeout(600);
  await page.getByRole("button", { name: "Detener", exact: true }).click();
  await expect(
    page.getByText("COMBATE DETENIDO", { exact: true }),
  ).toBeVisible();
  const stop = await (await request.get(`/api/v2/matches/${id}`)).json();
  await page.waitForTimeout(600);
  const final = await (await request.get(`/api/v2/matches/${id}`)).json();
  expect(final.players.map((p: any) => p.counts.accepted)).toEqual(
    stop.players.map((p: any) => p.counts.accepted),
  );
  expect(errors).toEqual([]);
});
test("keyboard human moves, remapping and focus loss pauses", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Entrenar", exact: true }).click();
  await page
    .getByRole("button", { name: "Iniciar combate", exact: true })
    .click();
  await page.waitForTimeout(1600);
  const id = (await (await request.get("/api/v2/matches")).json())[0].id;
  const before = await (await request.get(`/api/v2/matches/${id}`)).json();
  await page.keyboard.down("d");
  await page.waitForTimeout(350);
  await page.keyboard.up("d");
  await page.waitForTimeout(100);
  const after = await (await request.get(`/api/v2/matches/${id}`)).json();
  expect(after.state.fighters[0].x).toBeGreaterThan(before.state.fighters[0].x);
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  await expect(
    page.getByRole("button", { name: "Reanudar", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Ajustes", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  const light = page
    .locator(".key-grid button")
    .filter({ hasText: "Golpe ligero" });
  await light.focus();
  await page.keyboard.press("z");
  await expect(light).toContainText("Z");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
test("training clash decisions and cinematic finishers", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Entrenar", exact: true }).click();
  await page
    .getByText("EJERCICIO", { exact: false })
    .locator("select")
    .selectOption("clash");
  await page
    .getByRole("button", { name: "Iniciar combate", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "CHOQUE DE ENERGÍA" }),
  ).toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: /Sobrecargar/ }).click();
  await page.getByRole("button", { name: "Detener", exact: true }).click();
  await page
    .getByText("EJERCICIO", { exact: false })
    .locator("select")
    .selectOption("finisher");
  await page
    .getByRole("button", { name: "Iniciar combate", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Fénix incandescente", exact: true }),
  ).toBeVisible({ timeout: 10000 });
  await page
    .getByRole("button", { name: "Fénix incandescente", exact: true })
    .click();
  await expect(page.locator(".cinematic-title")).toContainText(
    "Fénix incandescente",
  );
  await page.getByRole("button", { name: "Omitir", exact: true }).click();

  await expect(
    page.getByText("FIN DEL COMBATE", { exact: true }),
  ).toBeVisible();
  const id = (await (await request.get("/api/v2/matches")).json())[0].id;
  const events = await (
    await request.get(`/api/v2/matches/${id}/events?limit=5000`)
  ).json();
  expect(
    events.some(
      (e: any) => e.kind === "combat" && e.event.kind === "finisher_choice",
    ),
  ).toBeTruthy();
});
test("replay and paired laboratory results are readable and require no inference", async ({
  page,
  request,
}) => {
  const response = await request.post("/api/v2/series", {
    data: { pairs: 1, match: { max_seconds: 2 } },
  });
  expect(response.ok()).toBeTruthy();
  const job = await response.json();
  await expect
    .poll(
      async () => {
        const jobs = await (await request.get("/api/v2/series")).json();
        return jobs.find((j: any) => j.id === job.id)?.status;
      },
      { timeout: 15000 },
    )
    .toBe("completed");
  await page.goto("/");
  await page.getByRole("button", { name: "Laboratorio", exact: true }).click();
  await expect(
    page.locator(".series-card").first().locator("tbody tr"),
  ).toHaveCount(2);
  await page.getByRole("button", { name: "Replays", exact: true }).click();
  await page.locator(".replay-list button").first().click();
  await expect(
    page.getByRole("button", { name: "Reproducir", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reproducir", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Pausar", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pausar", exact: true }).click();
  await page.getByLabel("Posición del replay").fill("1");
  await expect(
    page.getByRole("link", { name: "Exportar", exact: true }),
  ).toHaveAttribute("href", /export/);
});
test("mobile spectator layout has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Iniciar combate", exact: true }),
  ).toBeEnabled({ timeout: 30000 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: "/tmp/eclipse-mobile.png", fullPage: true });
});

test("standard gamepad buttons move the human and pause", async ({
  page,
  request,
}) => {
  await page.addInitScript(() => {
    const w = window as any;
    w.arenaPad = {
      connected: true,
      axes: [0, 0],
      buttons: Array.from({ length: 16 }, () => ({ pressed: false, value: 0 })),
    };
    Object.defineProperty(navigator, "getGamepads", {
      value: () => [w.arenaPad],
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Entrenar", exact: true }).click();
  await page
    .getByRole("button", { name: "Iniciar combate", exact: true })
    .click();
  await page.waitForTimeout(1500);
  const id = (await (await request.get("/api/v2/matches")).json())[0].id;
  const before = await (await request.get(`/api/v2/matches/${id}`)).json();
  await page.evaluate(() => {
    (window as any).arenaPad.axes[0] = 1;
  });
  await page.waitForTimeout(400);
  await page.evaluate(() => {
    (window as any).arenaPad.axes[0] = 0;
  });
  const after = await (await request.get(`/api/v2/matches/${id}`)).json();
  expect(after.state.fighters[0].x).toBeGreaterThan(before.state.fighters[0].x);
  await page.evaluate(() => {
    (window as any).arenaPad.buttons[9].pressed = true;
  });
  await expect(
    page.getByRole("button", { name: "Reanudar", exact: true }),
  ).toBeVisible();
});
