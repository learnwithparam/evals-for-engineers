// The text audit needs the review app for each step. Playwright starts both apps and stops them.
import { join } from "node:path";
import { defineConfig } from "@playwright/test";

const MARK_PORT = 8765;
const NOTE_PORT = 8766;
const ROOT = join(import.meta.dirname, "..");

export default defineConfig({
  testDir: ".",
  testMatch: "text-audit.spec.ts",
  reporter: "list",
  use: {
    // biome-ignore lint/style/useNamingConvention: baseURL is the name Playwright requires
    baseURL: `http://127.0.0.1:${MARK_PORT}`,
    trace: "off",
    // Set CHROMIUM_PATH to a Chromium you already have; otherwise Playwright uses its own.
    launchOptions: { executablePath: process.env.CHROMIUM_PATH },
  },
  webServer: [
    {
      command: `uv run review mark-the-traces --port ${MARK_PORT}`,
      cwd: ROOT,
      url: `http://127.0.0.1:${MARK_PORT}`,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `uv run review note-the-failures --port ${NOTE_PORT}`,
      cwd: ROOT,
      url: `http://127.0.0.1:${NOTE_PORT}`,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
