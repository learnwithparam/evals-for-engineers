// bun parts/03-judge-what-code-cannot/shoot.ts: captures the two pictures this part's steps show.
// It runs the real scripts in replay mode on a copy of each folder, renders the output as a dark
// terminal 800 pixels wide, and screenshots it, in the same style as images/shoot.ts.

import { cpSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium, type Page } from "playwright";

const PART = import.meta.dir;
const ROOT = join(PART, "..", "..");

const TERMINAL_STYLE = [
  "body{margin:0;background:#0f1412;padding:16px;width:800px;box-sizing:border-box}",
  ".w{background:#161c19;border-radius:8px;border:1px solid #2a332f;overflow:hidden}",
  ".t{padding:8px 12px;background:#1f2723;color:#8c9a93;font:12px system-ui}",
  "pre{margin:0;padding:14px 16px;color:#dfe7e2;" +
    "font:12.5px/1.5 ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap}",
  ".p{color:#7fd1a8}.bad{color:#ff8a80}</style>",
].join("\n");

const escapeHtml = (text: string) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;");

function terminal(command: string, output: string): string {
  const head = `<!doctype html><meta charset="utf-8"><style>\n${TERMINAL_STYLE}\n`;
  const title = '<div class="w"><div class="t">fernhill: ~/evals-for-engineers</div>';
  const prompt = `<pre><span class="p">$ ${escapeHtml(command)}</span>\n`;
  const coloured = escapeHtml(output).replace(
    /(judge (pass|fail))/g,
    '<span class="bad">$1</span>',
  );
  return `${head}${title}${prompt}${coloured}</pre></div>`;
}

/** Runs a script in a copy of a step folder, so the picture never changes the repo. */
function runInCopy(folder: string, script: string): string {
  const copy = mkdtempSync(join(tmpdir(), "shot-"));
  cpSync(join(PART, folder), copy, { recursive: true });
  const environment: Record<string, string | undefined> = { ...process.env };
  environment.LLM_PROVIDER = "replay";
  environment.PYTHONDONTWRITEBYTECODE = "1";
  const command = ["uv", "run", "--quiet", "--project", ROOT, "python", script];
  const finished = Bun.spawnSync(command, { cwd: copy, env: environment, stdout: "pipe" });
  return finished.stdout.toString().trimEnd();
}

type Shot = { folder: string; script: string; file: string };

async function shoot(page: Page, { folder, script, file }: Shot) {
  const output = runInCopy(folder, script);
  await page.setContent(terminal(`uv run python ${script}`, output));
  await page.locator(".w").screenshot({ path: join(PART, file) });
  console.log(`wrote ${file}`);
}

// Set CHROMIUM_PATH to use a Chromium you already have.
const executablePath = process.env.CHROMIUM_PATH;
const browser = await chromium.launch(executablePath ? { executablePath } : {});
const page = await browser.newPage({ viewport: { width: 832, height: 600 }, deviceScaleFactor: 2 });
await shoot(page, {
  folder: "01-label-the-answers/solution",
  script: "kappa.py",
  file: "01-label-the-answers/images/expected.png",
});
await shoot(page, {
  folder: "03-align-the-judge/wrong/kept-the-draft",
  script: "align.py",
  file: "03-align-the-judge/images/expected.png",
});
await browser.close();
