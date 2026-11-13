// bun parts/04-gate-the-change/images/shoot.ts: captures the pictures for Gate the change.
// It runs the sample answer for real, renders the output as a dark terminal 800 pixels wide,
// and screenshots it, in the same style as images/shoot.ts at the repo root.

import { join } from "node:path";
import { chromium } from "playwright";

const PART = join(import.meta.dir, "..");
const STEP = join(PART, "01-gate-the-release");

// Replay mode answers from recordings, so the picture never needs a key.
const environment: Record<string, string | undefined> = { ...process.env };
environment.LLM_PROVIDER = "replay";

function shell(command: string[], folder: string): string {
  const finished = Bun.spawnSync(command, {
    cwd: folder,
    env: environment,
    stdout: "pipe",
    stderr: "pipe",
  });
  return finished.stdout.toString();
}

const escapeHtml = (text: string) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;");

const TERMINAL_STYLE = [
  "body{margin:0;background:#0f1412;padding:16px;width:800px;box-sizing:border-box}",
  ".w{background:#161c19;border-radius:8px;border:1px solid #2a332f;overflow:hidden}",
  ".t{padding:8px 12px;background:#1f2723;color:#8c9a93;font:12px system-ui}",
  "pre{margin:0;padding:14px 16px;color:#dfe7e2;" +
    "font:12.5px/1.5 ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap}",
  ".p{color:#7fd1a8}.bad{color:#ff8a80}.ok{color:#7fd1a8}</style>",
].join("\n");

function colourWords(output: string): string {
  const escaped = escapeHtml(output);
  const withBad = escaped.replace(/"(block)"/g, '"<span class="bad">$1</span>"');
  return withBad.replace(/"(ship)"/g, '"<span class="ok">$1</span>"');
}

function terminal(command: string, output: string): string {
  const head = `<!doctype html><meta charset="utf-8"><style>\n${TERMINAL_STYLE}\n`;
  const title = '<div class="w"><div class="t">fernhill: ~/evals-for-engineers</div>';
  const prompt = `<pre><span class="p">$ ${escapeHtml(command)}</span>\n`;
  return `${head}${title}${prompt}${colourWords(output)}</pre></div>`;
}

// The full report lists all 50 cases; the picture shows the verdict, the reasons and one case.
function firstLines(output: string, count: number): string {
  const lines = output.trimEnd().split("\n");
  return `${lines.slice(0, count).join("\n")}\n  ...`;
}

// CHROMIUM_PATH points at a Chromium you already have, when Playwright's own is not installed.
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
const page = await browser.newPage({ viewport: { width: 832, height: 600 }, deviceScaleFactor: 2 });
const command = ["uv", "run", "--quiet", "python", "gate.py", "--release", "cheaper-model"];
const output = shell(command, join(STEP, "solution"));
await page.setContent(
  terminal("uv run python gate.py --release cheaper-model", firstLines(output, 14)),
);
const picture = join(STEP, "images", "expected.png");
await page.locator(".w").screenshot({ path: picture });
console.log(`wrote ${picture}`);
await browser.close();
