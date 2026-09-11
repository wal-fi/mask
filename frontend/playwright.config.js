import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

export default defineConfig({
  testDir: "./browser", timeout: 60000, workers: 1, retries: 0, fullyParallel: false,
  reporter: "./browser/reporter.js", outputDir: join(tmpdir(), "maskgw-browser-results"),
  use: { trace: "off", screenshot: "off", video: "off" },
  projects: ["chromium", "firefox", "webkit"].map(browserName => ({name: browserName})),
});
