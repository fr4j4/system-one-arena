const { chromium } = require("@playwright/test");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1080 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() =>
    localStorage.setItem(
      "eclipse-settings-v2",
      JSON.stringify({ quality: "medium", master: 0 }),
    ),
  );
  await page.goto("http://127.0.0.1:8012");
  await page
    .getByRole("button", { name: "Iniciar combate", exact: true })
    .waitFor();
  await page.waitForTimeout(2500);
  const report = {
    errors,
    renderer: await page.locator("canvas").evaluate((c) => {
      const gl = c.getContext("webgl2");
      const e = gl.getExtension("WEBGL_debug_renderer_info");
      return {
        gpu: e
          ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL)
          : gl.getParameter(gl.RENDERER),
        ...c.dataset,
      };
    }),
    samples: [],
  };
  await page.screenshot({
    path: "/tmp/eclipse-final-preview.png",
    fullPage: true,
  });
  for (const fighter of ["Terra", "Nyx", "Ember", "Flux", "Terra", "Nyx"]) {
    await page
      .getByRole("button", { name: "P1 " + fighter, exact: true })
      .click();
    await page
      .getByRole("button", { name: "Iniciar combate", exact: true })
      .waitFor();
    await page.waitForTimeout(1000);
    report.samples.push(
      await page.locator("canvas").evaluate((c) => ({ ...c.dataset })),
    );
  }
  await page.locator(".match-options select").first().selectOption("reactor");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "/tmp/eclipse-reactor.png", fullPage: true });
  console.log(JSON.stringify(report, null, 2));
  require("fs").writeFileSync(
    "/tmp/eclipse-visual-audit.json",
    JSON.stringify(report, null, 2),
  );
  await browser.close();
})();
