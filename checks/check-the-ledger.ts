import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { once, runPython } from "./lib/run";
import { plantedFaults } from "./lib/world";

// The learner writes each problem, so every field may be missing or have the wrong type.
type Problem = { month?: unknown; problem?: unknown; [field: string]: unknown };

const RENT_PROBLEM = "rent_not_as_lease";
const PET_PROBLEM = "pet_fee_but_no_pets";

// Run the learner's check into a temp file, never over their own output.
function problemsFound(folder: string): Problem[] | null {
  const scratch = mkdtempSync(join(tmpdir(), "ledger-"));
  const out = join(scratch, "ledger_problems.jsonl");
  const ran = runPython("ledger_check.py", ["--out", out], folder);
  if (ran.code !== 0 || !existsSync(out)) return null;
  const lines = readFileSync(out, "utf8").split("\n");
  const filled = lines.filter((line) => line.trim());
  return filled.map((line) => JSON.parse(line) as Problem);
}

const found = once(problemsFound);

/** Planted ledger faults: 4 is a pet fee where pets are banned, 6 a rent step never charged. */
function plantedLeases(fault: number): string[] {
  const inLedger = plantedFaults().filter((planted) => planted.system === "ledger");
  return inLedger.filter((planted) => planted.fault === fault).map((planted) => planted.ref);
}

function leasesFlagged(folder: string, kind: string): Set<string> {
  const problems = found(folder) ?? [];
  const ofKind = problems.filter((problem) => problem.problem === kind);
  return new Set(ofKind.map((problem) => String(problem.lease_id)));
}

function findsEvery(folder: string, fault: number, kind: string): boolean {
  const flagged = leasesFlagged(folder, kind);
  return plantedLeases(fault).every((leaseId) => flagged.has(leaseId));
}

function noFalseAlarm(folder: string): boolean {
  const problems = found(folder);
  if (!problems) return false;
  const planted = new Set([...plantedLeases(4), ...plantedLeases(6)]);
  return problems.every((problem) => planted.has(String(problem.lease_id)));
}

function everyProblemIsComplete(folder: string): boolean {
  const problems = found(folder);
  if (!problems || problems.length === 0) return false;
  return problems.every(
    (problem) =>
      typeof problem.lease_id === "string" &&
      /^\d{4}-\d{2}$/.test(String(problem.month)) &&
      (problem.problem === RENT_PROBLEM || problem.problem === PET_PROBLEM) &&
      typeof problem.charged === "number" &&
      typeof problem.lease_says === "number",
  );
}

export default [
  {
    says: "ledger_check.py runs and writes its problems",
    test: (folder) => found(folder) !== null,
    tryNext:
      "run uv run python ledger_check.py and read the error; " +
      "NotImplementedError means a function is still the starter",
  },
  {
    says: "every problem names the lease, month, kind, the amount charged and what the lease says",
    test: everyProblemIsComplete,
    tryNext:
      'write each problem as {"lease_id", "month": "2026-01", "problem": ' +
      '"rent_not_as_lease" or "pet_fee_but_no_pets", "charged", "lease_says"}',
  },
  {
    says: "finds every lease whose rent step was never charged",
    test: (folder) => findsEvery(folder, 6, RENT_PROBLEM),
    tryNext:
      "take the rent steps from keys.jsonl, the approved abstracts; " +
      "the system of record dropped the steps, so it hides this fault",
  },
  {
    says: "finds every lease charged a pet fee where pets are banned",
    test: (folder) => findsEvery(folder, 4, PET_PROBLEM),
    tryNext: 'flag any month with a "pet_fee" charge on a lease whose pets_allowed is false',
  },
  {
    says: "no false alarm on a clean lease",
    test: noFalseAlarm,
    tryNext:
      "an amendment changes the rent only from its effective month; " +
      "before that, the original rent is right",
  },
] satisfies Rule[];
