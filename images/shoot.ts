// bun run shots: captures every picture the READMEs show, from the real system in replay mode.
// Terminal output is rendered as HTML in a dark terminal style, 800 pixels wide, then screenshotted.
// Needs a Chromium: `bunx playwright install chromium`, or set CHROMIUM_PATH to one you have.

import { join } from "node:path";
import { chromium, type Page } from "playwright";

const ROOT = join(import.meta.dir, "..");
const env = { ...process.env, LLM_PROVIDER: "replay" };
const sh = (cmd: string[]) => {
  const p = Bun.spawnSync(cmd, { cwd: ROOT, env, stdout: "pipe", stderr: "pipe" });
  return p.stdout.toString().replace(/\x1b\[[0-9;]*m/g, "");
};
const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
const terminal = (cmd: string, out: string) => `<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#0f1412;padding:16px;width:800px;box-sizing:border-box}
.w{background:#161c19;border-radius:8px;border:1px solid #2a332f;overflow:hidden}
.t{padding:8px 12px;background:#1f2723;color:#8c9a93;font:12px system-ui}
pre{margin:0;padding:14px 16px;color:#dfe7e2;font:12.5px/1.5 ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap}
.p{color:#7fd1a8}.bad{color:#ff8a80}.ok{color:#7fd1a8}</style>
<div class="w"><div class="t">fernhill: ~/evals-for-engineers</div><pre><span class="p">$ ${esc(cmd)}</span>
${esc(out)
  .replace(/\b(WRONG|BLOCKED|FAIL)\b/g, '<span class="bad">$1</span>')
  .replace(/\b(PASS|SHIP)\b/g, '<span class="ok">$1</span>')}</pre></div>`;

async function shootTerminal(page: Page, cmd: string[], shown: string, file: string) {
  await page.setContent(terminal(shown, sh(cmd).trimEnd()));
  await page.locator(".w").screenshot({ path: join(ROOT, file) });
  console.log(`wrote ${file}`);
}

const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
);
const page = await browser.newPage({ viewport: { width: 832, height: 600 }, deviceScaleFactor: 2 });

sh(["uv", "run", "--quiet", "world", "reset"]);
await shootTerminal(
  page,
  ["uv", "run", "--quiet", "fernhill", "report"],
  "uv run fernhill report",
  "images/finished-system.png",
);
await shootTerminal(
  page,
  ["uv", "run", "--quiet", "fernhill", "demo"],
  "uv run fernhill demo",
  "00-orientation/images/demo.png",
);
await shootTerminal(
  page,
  ["uv", "run", "--quiet", "fernhill", "report", "--out", "world/runs/report.txt"],
  "uv run fernhill report --out 00-orientation/01-meet-fernhill/problem/report.txt",
  "00-orientation/01-meet-fernhill/images/expected.png",
);

// The review app, opened on the sample answer of mark-the-traces, showing an amended lease marked fail.
const app = Bun.spawn(
  [
    "uv",
    "run",
    "--quiet",
    "python",
    "-c",
    "import sys; from fernhill.review import server as s; from pathlib import Path; " +
      "s.step_dir = lambda n: s.paths.ROOT / 'parts/01-find-the-failures/02-mark-the-traces/solution'; " +
      "sys.argv = ['review', 'x', '--port', '8791']; s.main()",
  ],
  { cwd: ROOT, env, stdout: "ignore", stderr: "ignore" },
);
await Bun.sleep(2500);
const shot = await browser.newPage({
  viewport: { width: 1280, height: 800 },
  deviceScaleFactor: 2,
  colorScheme: "light",
});
await shot.goto("http://127.0.0.1:8791");
await shot.waitForSelector("#abs tr");
const amendedFail = await shot.evaluate(() =>
  fetch("/api/state")
    .then((r) => r.json())
    .then((s: any) => s.items.findIndex((x: any) => x.trace.amendments > 0 && x.mark === "fail")),
);
for (let i = 0; i < amendedFail; i++) await shot.keyboard.press("ArrowRight");
await shot.evaluate(() => {
  const p = document.getElementById("lease")!;
  p.scrollTop = p.scrollHeight;
});
await shot.screenshot({
  path: join(ROOT, "parts/01-find-the-failures/02-mark-the-traces/images/expected.png"),
});
console.log("wrote parts/01-find-the-failures/02-mark-the-traces/images/expected.png");
app.kill();
await browser.close();
