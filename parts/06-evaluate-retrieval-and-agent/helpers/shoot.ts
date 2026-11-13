// Captures the pictures of Evaluate retrieval and the agent from the real scripts in replay mode.
// Terminal output is drawn as HTML in a dark terminal style, 800 pixels wide, then captured.
// Run from the repo root: bun parts/06-evaluate-retrieval-and-agent/helpers/shoot.ts
// The supervisor may fold these shots into images/shoot.ts.

import { join } from "node:path";
import { chromium, type Page } from "playwright";

const ROOT = join(import.meta.dir, "..", "..", "..");
const PART = "parts/06-evaluate-retrieval-and-agent";

// Replay mode answers from recordings, so the pictures never need a key and never change.
const environment: Record<string, string | undefined> = { ...process.env };
environment.LLM_PROVIDER = "replay";

type TerminalShot = { folder: string; command: string[]; shown: string; file: string };

const SHOTS: TerminalShot[] = [
  {
    folder: `${PART}/01-measure-retrieval-recall/solution`,
    command: ["uv", "run", "--quiet", "python", "recall.py"],
    shown: "uv run python recall.py",
    file: `${PART}/01-measure-retrieval-recall/images/expected.png`,
  },
];

function shell(command: string[], folder: string): string {
  const finished = Bun.spawnSync(command, {
    cwd: join(ROOT, folder),
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
  ".p{color:#7fd1a8}.bad{color:#ff8a80}.ok{color:#7fd1a8}",
].join("\n");

function colourWords(output: string): string {
  const escaped = escapeHtml(output);
  const withBad = escaped.replace(/\b(ALERT|FAIL|fail)\b/g, '<span class="bad">$1</span>');
  return withBad.replace(/\b(PASS|pass)\b/g, '<span class="ok">$1</span>');
}

function terminalPage(command: string, output: string): string {
  const head = `<!doctype html><meta charset="utf-8"><style>\n${TERMINAL_STYLE}\n</style>`;
  const title = '<div class="w"><div class="t">fernhill: ~/evals-for-engineers</div>';
  const prompt = `<pre><span class="p">$ ${escapeHtml(command)}</span>\n`;
  return `${head}${title}${prompt}${colourWords(output)}</pre></div>`;
}

async function shootTerminal(page: Page, shot: TerminalShot) {
  const output = shell(shot.command, shot.folder).trimEnd();
  await page.setContent(terminalPage(shot.shown, output));
  await page.locator(".w").screenshot({ path: join(ROOT, shot.file) });
  console.log(`wrote ${shot.file}`);
}

// Set CHROMIUM_PATH to use a Chromium you already have.
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
const page = await browser.newPage({ viewport: { width: 832, height: 600 }, deviceScaleFactor: 2 });
for (const shot of SHOTS) await shootTerminal(page, shot);
await browser.close();
