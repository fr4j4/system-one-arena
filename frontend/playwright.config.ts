import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:8013",
    viewport: { width: 1440, height: 1080 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "../.venv/bin/uvicorn arena.app:app --host 127.0.0.1 --port 8013",
    url: "http://127.0.0.1:8013/api/health",
    reuseExistingServer: false,
    env: { ARENA_FRONTEND_DIR: "dist", COMBAT_DATA_DIR: "../data/combat-e2e", LAYA_ENABLED: "false" },
  },
});
