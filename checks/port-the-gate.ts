import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { ROOT } from "./lib/world";

// The learner works in assignment/. problem/ holds only the README that points there.
function workFolder(folder: string): string {
  return folder.endsWith("/problem") ? join(ROOT, "assignment") : folder;
}

type Verdicts = Record<string, string>;
const cache = new Map<string, Verdicts>();

// One run of checks/assignment.py answers every rule, so run it once per folder.
function verdicts(folder: string): Verdicts {
  const work = workFolder(folder);
  const known = cache.get(work);
  if (known) return known;
  const command = ["uv", "run", "--quiet", "checks/assignment.py", "--dir", work];
  Bun.spawnSync(command, { cwd: ROOT, stdout: "pipe", stderr: "pipe", timeout: 120_000 });
  const resultPath = join(work, "result.json");
  const result = existsSync(resultPath) ? JSON.parse(readFileSync(resultPath, "utf8")) : {};
  const found: Verdicts = result.lines ?? {};
  cache.set(work, found);
  return found;
}

const passes = (line: string) => (folder: string) => verdicts(folder)[line] === "pass";

const rules: Rule[] = [
  {
    says: "inspect-ai resolves to 0.3.289",
    test: passes("inspect-ai resolves to 0.3.289"),
    tryNext: "Run uv sync, then check pyproject.toml pins inspect-ai==0.3.289.",
  },
  {
    says: "an eval log has one score per dataset row",
    test: passes("an eval log has one score per dataset row"),
    tryNext: "Run the inspect eval command from the README so assignment/logs holds a log.",
  },
  {
    says: "the failing rows match the hand-built gate",
    test: passes("the failing rows match the hand-built gate"),
    tryNext: "Port the course grader as the scorer, with the critical fields only.",
  },
];

export default rules;
