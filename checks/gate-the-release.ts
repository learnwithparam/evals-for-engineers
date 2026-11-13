import { existsSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { runPython } from "./lib/run";
import { DATA, type JsonRecord, readJsonl } from "./lib/world";

// The learner's gate prints this report. Every field may be missing or the wrong type.
export type GateReport = { verdict?: unknown; reasons?: unknown; cases?: unknown };
export type GateRun = { code: number; report: GateReport | undefined };

// The gate leases the check breaks on purpose: one times out, one has no rows at all.
const TIMED_OUT_LEASE = "L040";
const MISSING_LEASE = "L012";

function parseReport(output: string): GateReport | undefined {
  try {
    return JSON.parse(output) as GateReport;
  } catch {
    return undefined;
  }
}

const cachedRuns = new Map<string, GateRun>();

/** Runs `gate.py --release <release>` in the learner's folder once, and keeps the result. */
export function runGate(folder: string, release: string): GateRun {
  const cacheKey = `${folder}|${release}`;
  const cached = cachedRuns.get(cacheKey);
  if (cached) return cached;
  const ran = runPython("gate.py", ["--release", release], folder, 120_000);
  const result = { code: ran.code, report: parseReport(ran.out) };
  cachedRuns.set(cacheKey, result);
  return result;
}

/** A copy of a real release with one change, written to a temp file the gate reads by path. */
export function changedRelease(change: (rows: JsonRecord[]) => JsonRecord[]): string {
  const rows = readJsonl(join(DATA, "releases", "clause-ids-in-answer.jsonl"));
  const lines = change(rows).map((row) => JSON.stringify(row));
  const folder = mkdtempSync(join(tmpdir(), "release-"));
  const path = join(folder, "changed.jsonl");
  writeFileSync(path, `${lines.join("\n")}\n`);
  return path;
}

function withTimeout(rows: JsonRecord[]): JsonRecord[] {
  return rows.map((row) => {
    if (row.kind !== "abstract" || row.lease_id !== TIMED_OUT_LEASE) return row;
    return { ...row, output: null, error: "timeout" };
  });
}

const withoutLease = (rows: JsonRecord[]) => rows.filter((row) => row.lease_id !== MISSING_LEASE);

// Made once per check run, so every folder reads the same broken releases.
let timeoutRelease: string | undefined;
let missingRelease: string | undefined;
const timeoutPath = () => {
  timeoutRelease ??= changedRelease(withTimeout);
  return timeoutRelease;
};
const missingPath = () => {
  missingRelease ??= changedRelease(withoutLease);
  return missingRelease;
};

export function blocks(run: GateRun): boolean {
  return run.code === 1 && run.report?.verdict === "block";
}

export function ships(run: GateRun): boolean {
  return run.code === 0 && run.report?.verdict === "ship";
}

function reasonsMention(run: GateRun, words: RegExp): boolean {
  const reasons = run.report?.reasons;
  if (!Array.isArray(reasons)) return false;
  return reasons.some((reason) => words.test(String(reason)));
}

export default [
  {
    says: "gate.py exists",
    test: (folder) => existsSync(join(folder, "gate.py")),
    tryNext: "keep gate.py in this problem folder and edit it there",
  },
  {
    says: "the gate ships live, the release it compares against",
    test: (folder) => ships(runGate(folder, "live")),
    tryNext:
      "run uv run python gate.py --release live; it must print a JSON report " +
      'with "verdict": "ship" and exit 0',
  },
  {
    says: "the gate blocks cheaper-model with exit 1, and a reason names the rent",
    test: (folder) => {
      const run = runGate(folder, "cheaper-model");
      return blocks(run) && reasonsMention(run, /rent/i);
    },
    tryNext:
      "the average hides it: compare each critical field per lease with live, " +
      "and block when one live got right is now wrong",
  },
  {
    says: "the gate blocks shorter-prompt, which stops saying 'The lease does not say.'",
    test: (folder) => blocks(runGate(folder, "shorter-prompt")),
    tryNext:
      "read the desk rows too: block when a question live answered with " +
      "'The lease does not say.' no longer gets that answer",
  },
  {
    says: "the gate ships clause-ids-in-answer, a harmless change",
    test: (folder) => ships(runGate(folder, "clause-ids-in-answer")),
    tryNext:
      "block only on critical fields that got worse than live, " +
      "not on fields that were already wrong",
  },
  {
    says: "the gate blocks when a case times out (it fails closed)",
    test: (folder) => blocks(runGate(folder, timeoutPath())),
    tryNext:
      'a row with "output": null and an "error" has no result; count that lease as missing ' +
      "and block, never skip it",
  },
  {
    says: "the gate blocks when a gate lease has no result at all",
    test: (folder) => blocks(runGate(folder, missingPath())),
    tryNext: "check every lease in splits.json gate has a result, and block on any that does not",
  },
] satisfies Rule[];
