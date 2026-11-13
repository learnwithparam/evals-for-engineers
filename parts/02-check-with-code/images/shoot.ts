// bun parts/02-check-with-code/images/shoot.ts: captures the pictures this part's steps show.
// It runs the real sample answer, renders the output as a dark terminal 800 pixels wide,
// and screenshots it. Same look as images/shoot.ts at the repo root.

import { join } from "node:path";
import { chromium } from "playwright";

const ROOT = join(import.meta.dir, "..", "..", "..");
const PART = join(ROOT, "parts", "02-check-with-code");

type Shot = { folder: string; command: string[]; shown: string; file: string };

const SHOTS: Shot[] = [
  {
    folder: join(PART, "02-write-field-checks", "solution"),
    command: ["uv", "run", "--quiet", "python", "checks.py", "--golden", "golden.jsonl", "--out"],
    shown: "uv run python checks.py --golden golden.jsonl",
    file: join(PART, "02-write-field-checks", "images", "expected.png"),
  },
];

const TERMINAL_STYLE = [
  "body{margin:0;background:#0f1412;padding:16px;width:800px;box-sizing:border-box}",
  ".window{background:#161c19;border-radius:8px;border:1px solid #2a332f;overflow:hidden}",
  ".title{padding:8px 12px;background:#1f2723;color:#8c9a93;font:12px system-ui}",
  "pre{margin:0;padding:14px 16px;color:#dfe7e2;" +
    "font:12.5px/1.5 ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap}",
  ".prompt{color:#7fd1a8}",
].join("\n");

const escapeHtml = (text: string) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;");

// Replay mode answers from recordings, so the pictures never need a key.
function replayEnvironment(): Record<string, string | undefined> {
  const environment: Record<string, string | undefined> = { ...process.env };
  environment.LLM_PROVIDER = "replay";
  return environment;
}

// The output file goes to a scratch path, so taking a picture never changes the sample answer.
function outputOf(shot: Shot): string {
  const scratchFile = join(Bun.env.TMPDIR ?? "/tmp", "shot-output.json");
  const finished = Bun.spawnSync([...shot.command, scratchFile], {
    cwd: shot.folder,
    env: replayEnvironment(),
    stdout: "pipe",
  });
  const output = finished.stdout.toString().trimEnd();
  return output.replace(scratchFile, "accuracy.json").replace("shot-output.json", "accuracy.json");
}

function terminalPage(shot: Shot): string {
  const head = `<!doctype html><meta charset="utf-8"><style>${TERMINAL_STYLE}</style>`;
  const title = '<div class="window"><div class="title">fernhill: ~/evals-for-engineers</div>';
  const prompt = `<pre><span class="prompt">$ ${escapeHtml(shot.shown)}</span>\n`;
  return `${head}${title}${prompt}${escapeHtml(outputOf(shot))}</pre></div>`;
}

// Use a Chromium you already have with CHROMIUM_PATH, or the one Playwright installed.
const browser = await chromium.launch({ executablePath: Bun.env.CHROMIUM_PATH });
const page = await browser.newPage({ viewport: { width: 832, height: 600 }, deviceScaleFactor: 2 });
for (const shot of SHOTS) {
  await page.setContent(terminalPage(shot));
  await page.locator(".window").screenshot({ path: shot.file });
  console.log(`wrote ${shot.file}`);
}
await browser.close();
