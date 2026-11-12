// bun run shots: captures every picture the READMEs show, from the real system in replay mode.
// Terminal output is rendered as HTML in a dark terminal style, 800 pixels wide,
// then screenshotted.
// Needs a Chromium: `bunx playwright install chromium`, or set CHROMIUM_PATH to one you have.

import { join } from "node:path";
import { type Browser, chromium, type Page } from "playwright";

const ROOT = join(import.meta.dir, "..");
const REVIEW_STEP = "parts/01-find-the-failures/02-mark-the-traces";

// Replay mode answers from recordings, so the pictures never need a key and never change.
const environment: Record<string, string | undefined> = { ...process.env };
environment.LLM_PROVIDER = "replay";

// Terminal colour codes start with the escape character; the HTML page draws its own colours.
const ESCAPE = String.fromCharCode(27);
const COLOUR_CODE = new RegExp(`${ESCAPE}\\[[0-9;]*m`, "g");

function shell(command: string[]): string {
  const finished = Bun.spawnSync(command, {
    cwd: ROOT,
    env: environment,
    stdout: "pipe",
    stderr: "pipe",
  });
  return finished.stdout.toString().replace(COLOUR_CODE, "");
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
  const withBad = escaped.replace(/\b(WRONG|BLOCKED|FAIL)\b/g, '<span class="bad">$1</span>');
  return withBad.replace(/\b(PASS|SHIP)\b/g, '<span class="ok">$1</span>');
}

function terminal(command: string, output: string): string {
  const head = `<!doctype html><meta charset="utf-8"><style>\n${TERMINAL_STYLE}\n`;
  const title = '<div class="w"><div class="t">fernhill: ~/evals-for-engineers</div>';
  const prompt = `<pre><span class="p">$ ${escapeHtml(command)}</span>\n`;
  return `${head}${title}${prompt}${colourWords(output)}</pre></div>`;
}

type TerminalShot = { command: string[]; shown: string; file: string };

async function shootTerminal(page: Page, { command, shown, file }: TerminalShot) {
  await page.setContent(terminal(shown, shell(command).trimEnd()));
  await page.locator(".w").screenshot({ path: join(ROOT, file) });
  console.log(`wrote ${file}`);
}

async function shootTerminals(browser: Browser) {
  const page = await browser.newPage({
    viewport: { width: 832, height: 600 },
    deviceScaleFactor: 2,
  });
  shell(["uv", "run", "--quiet", "world", "reset"]);
  await shootTerminal(page, {
    command: ["uv", "run", "--quiet", "fernhill", "report"],
    shown: "uv run fernhill report",
    file: "images/finished-system.png",
  });
  await shootTerminal(page, {
    command: ["uv", "run", "--quiet", "fernhill", "demo"],
    shown: "uv run fernhill demo",
    file: "00-orientation/images/demo.png",
  });
  await shootTerminal(page, {
    command: ["uv", "run", "--quiet", "fernhill", "report", "--out", "world/runs/report.txt"],
    shown: "uv run fernhill report --out 00-orientation/01-meet-fernhill/problem/report.txt",
    file: "00-orientation/01-meet-fernhill/images/expected.png",
  });
}

// Points the review app at the sample answer instead of the learner's folder, on a spare port.
const REVIEW_SERVER = [
  "import sys; from fernhill.review import server as s; from pathlib import Path; ",
  `s.step_dir = lambda _step: s.paths.ROOT / '${REVIEW_STEP}/solution'; `,
  "sys.argv = ['review', 'x', '--port', '8791']; s.main()",
].join("");

function startReviewApp() {
  return Bun.spawn(["uv", "run", "--quiet", "python", "-c", REVIEW_SERVER], {
    cwd: ROOT,
    env: environment,
    stdout: "ignore",
    stderr: "ignore",
  });
}

type ReviewState = { items: { trace: { amendments: number }; mark: string }[] };

// Runs inside the browser, so it fetches the app's own state instead of reading files.
async function firstAmendedFail(): Promise<number> {
  const response = await fetch("/api/state");
  const state = (await response.json()) as ReviewState;
  return state.items.findIndex((item) => item.trace.amendments > 0 && item.mark === "fail");
}

function scrollLeaseToEnd() {
  const leasePane = document.getElementById("lease");
  if (!leasePane) throw new Error("the review app has no #lease pane");
  leasePane.scrollTop = leasePane.scrollHeight;
}

// The review app, opened on the sample answer of mark-the-traces,
// showing an amended lease marked fail.
async function shootReviewApp(browser: Browser) {
  const app = startReviewApp();
  await Bun.sleep(2500);
  const shot = await browser.newPage({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2,
    colorScheme: "light",
  });
  await shot.goto("http://127.0.0.1:8791");
  await shot.waitForSelector("#abs tr");
  const amendedFail = await shot.evaluate(firstAmendedFail);
  for (let i = 0; i < amendedFail; i++) await shot.keyboard.press("ArrowRight");
  await shot.evaluate(scrollLeaseToEnd);
  await shot.screenshot({ path: join(ROOT, REVIEW_STEP, "images/expected.png") });
  console.log(`wrote ${REVIEW_STEP}/images/expected.png`);
  app.kill();
}

const executablePath = process.env.CHROMIUM_PATH;
const browser = await chromium.launch(executablePath ? { executablePath } : {});
await shootTerminals(browser);
await shootReviewApp(browser);
await browser.close();
