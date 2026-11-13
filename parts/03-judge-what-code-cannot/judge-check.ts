// Shared by the five checks of Judge what code cannot. It builds the judge inputs from the
// world, runs the learner's judge command in replay mode, and does the sums the checks compare.
// The checks never import the learner's Python: they only run run.py and read its output.

import { join } from "node:path";
import { python } from "../../checks/lib/run";
import { DATA, type JsonRecord, ROOT, readCsv, readJsonl } from "../../checks/lib/world";

export type JudgeInput = { id: string; question: string; answer: string; [field: string]: unknown };
export type Verdict = { id?: unknown; verdict?: unknown; critique?: unknown };
export type Pair = { dana: string; judge: string };

// The world's own copy of cases.py, so a changed copy in the learner's folder cannot change
// what the check feeds the judge.
const CASES_SCRIPT = join(import.meta.dir, "02-write-the-judge", "solution", "cases.py");

/** Python with the course's packages, even when run from a temp folder outside the repo. */
function pythonCommand(): string[] {
  const command = python();
  if (command[0] !== "uv") return command;
  return ["uv", "run", "--quiet", "--project", ROOT, "python"];
}

function replayEnvironment(): Record<string, string | undefined> {
  const environment: Record<string, string | undefined> = { ...process.env };
  environment.LLM_PROVIDER = "replay";
  environment.PYTHONDONTWRITEBYTECODE = "1";
  return environment;
}

type Finished = { code: number; out: string };

function spawn(command: string[], folder: string, input = ""): Finished {
  const finished = Bun.spawnSync(command, {
    cwd: folder,
    env: replayEnvironment(),
    stdin: Buffer.from(input),
    stdout: "pipe",
    stderr: "pipe",
    timeout: 300_000,
  });
  return { code: finished.exitCode ?? -1, out: finished.stdout.toString() };
}

const parseLines = <Shape>(text: string): Shape[] => {
  const filled = text.split("\n").filter((line) => line.trim());
  return filled.map((line) => JSON.parse(line) as Shape);
};

const inputCache = new Map<string, string>();

/** The judge inputs for one split, as JSON lines: train, dev, test or unlabelled. */
export function judgeInputText(split: string): string {
  const cached = inputCache.get(split);
  if (cached !== undefined) return cached;
  const finished = spawn([...pythonCommand(), CASES_SCRIPT, split], ROOT);
  inputCache.set(split, finished.out);
  return finished.out;
}

export const judgeInputs = (split: string) => parseLines<JudgeInput>(judgeInputText(split));
export const idsIn = (split: string) => judgeInputs(split).map((input) => input.id);

/** Runs the learner's judge on one split. Returns undefined when it fails or prints bad JSON. */
export function runJudge(folder: string, split: string): Verdict[] | undefined {
  const finished = spawn([...pythonCommand(), "run.py"], folder, judgeInputText(split));
  if (finished.code !== 0) return undefined;
  try {
    return parseLines<Verdict>(finished.out);
  } catch {
    return undefined;
  }
}

/** Runs any script in the learner's folder with replay on. */
export const runScript = (folder: string, script: string, args: string[] = []) =>
  spawn([...pythonCommand(), script, ...args], folder);

/** Dana's grounded labels: trace id to "pass" or "fail". */
export function danaLabels(): Map<string, string> {
  const rows = readCsv(join(DATA, "labels", "grounded.csv"));
  return new Map(rows.map((row) => [row.trace_id, row.label]));
}

/** The verdict for each id, only when every id is answered exactly once with pass or fail. */
export function verdictsById(verdicts: Verdict[] | undefined, ids: string[]) {
  if (!verdicts || verdicts.length !== ids.length) return undefined;
  const byId = new Map<string, string>();
  for (const verdict of verdicts) byId.set(String(verdict.id), String(verdict.verdict));
  const everyIdOnce = byId.size === ids.length && ids.every((id) => byId.has(id));
  return everyIdOnce ? byId : undefined;
}

export function pairsFor(byId: Map<string, string>): Pair[] {
  const dana = danaLabels();
  const ids = [...byId.keys()];
  return ids.map((id) => ({ dana: dana.get(id) ?? "", judge: byId.get(id) ?? "" }));
}

/** TPR: of Dana's passes, the share the judge passes. TNR: of Dana's fails, the share it fails. */
export function tprTnr(pairs: Pair[]): { tpr: number; tnr: number } {
  const danaPasses = pairs.filter((pair) => pair.dana === "pass");
  const danaFails = pairs.filter((pair) => pair.dana === "fail");
  const judgePasses = danaPasses.filter((pair) => pair.judge === "pass").length;
  const judgeFails = danaFails.filter((pair) => pair.judge === "fail").length;
  const tpr = danaPasses.length ? judgePasses / danaPasses.length : 0;
  const tnr = danaFails.length ? judgeFails / danaFails.length : 0;
  return { tpr, tnr };
}

export const near = (value: unknown, expected: number, tolerance = 0.01) =>
  typeof value === "number" && Math.abs(value - expected) <= tolerance;

/** The truth behind every lease desk run, including which planted fault it carries. */
export function deskTruth(): Map<string, JsonRecord> {
  const rows = readJsonl(join(DATA, "labels", "lease_desk_truth.jsonl"));
  return new Map(rows.map((row) => [row.trace_id as string, row]));
}

const words = (text: string) => text.toLowerCase().match(/[a-z0-9']+/g) ?? [];

function eightWordRuns(text: string): Set<string> {
  const allWords = words(text);
  const runs = new Set<string>();
  for (let i = 0; i + 8 <= allWords.length; i++) runs.add(allWords.slice(i, i + 8).join(" "));
  return runs;
}

/**
 * Text from a dev or test answer that the prompt copies: a trace id, or a run of 8 words that
 * no train answer shares. Answers follow templates, so runs shared with train are allowed.
 */
export function heldOutTextIn(prompt: string): string | undefined {
  const trainAnswers = judgeInputs("train").map((input) => input.answer);
  const trainRuns = eightWordRuns(trainAnswers.join("\n\n"));
  const promptRuns = eightWordRuns(prompt);
  const copiedRun = (answer: string) =>
    [...eightWordRuns(answer)].find((run) => promptRuns.has(run) && !trainRuns.has(run));
  for (const input of [...judgeInputs("dev"), ...judgeInputs("test")]) {
    if (prompt.includes(input.id)) return input.id;
    const copied = copiedRun(input.answer);
    if (copied) return copied;
  }
  return undefined;
}
