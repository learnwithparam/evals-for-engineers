import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { blocks, changedRelease, type GateRun, runGate, ships } from "./gate-the-release";
import { type JsonRecord, splits } from "./lib/world";

const TRIALS = 3;
const SHARE = 2;
const CRITICAL = ["monthly_rent", "rent_steps", "deposit", "renewal_notice_days"];
const HARMLESS = "clause-ids-in-answer";

// One case in the learner's report: case, field, trials, pass_at_3, pass_hat_3 and passed.
// The keys come from Python, so they are snake_case, and every one may be missing.
type Case = JsonRecord;

function casesOf(run: GateRun): Case[] {
  const cases = run.report?.cases;
  return Array.isArray(cases) ? (cases as Case[]) : [];
}

const harmlessCases = (folder: string) => casesOf(runGate(folder, HARMLESS));

const caseName = (oneCase: Case) => String(oneCase.case ?? oneCase.lease_id ?? "");

function trialsOf(oneCase: Case): boolean[] | undefined {
  const trials = oneCase.trials;
  if (!Array.isArray(trials)) return undefined;
  if (!trials.every((trial) => typeof trial === "boolean")) return undefined;
  return trials as boolean[];
}

const close = (reported: unknown, expected: number) =>
  typeof reported === "number" && Math.abs(reported - expected) < 0.001;

function numbersMatch(oneCase: Case): boolean {
  const trials = trialsOf(oneCase);
  if (!trials || trials.length === 0) return false;
  const right = trials.filter(Boolean).length;
  const shareRight = right / trials.length;
  const passAtThree = 1 - (1 - shareRight) ** TRIALS;
  const passHatThree = shareRight ** TRIALS;
  return close(oneCase.pass_at_3, passAtThree) && close(oneCase.pass_hat_3, passHatThree);
}

function passedMatchesShare(oneCase: Case): boolean {
  const trials = trialsOf(oneCase) ?? [];
  const right = trials.filter(Boolean).length;
  return oneCase.passed === right >= SHARE;
}

function findCase(folder: string, lease: string, field: string): Case | undefined {
  const cases = harmlessCases(folder);
  return cases.find((oneCase) => caseName(oneCase) === lease && oneCase.field === field);
}

function coversEveryGateCase(folder: string): boolean {
  const cases = harmlessCases(folder);
  for (const lease of splits().gate) {
    for (const field of CRITICAL) {
      const found = cases.find((oneCase) => caseName(oneCase) === lease && oneCase.field === field);
      if (!found) return false;
    }
  }
  return true;
}

// The flaky lease gets its rent wrong in one trial of three on the harmless release.
const flakyLease = () => (splits() as unknown as JsonRecord).flaky_gate_lease as string;

function withOneTrialLost(rows: JsonRecord[]): JsonRecord[] {
  return rows.filter(
    (row) => !(row.kind === "abstract" && row.lease_id === "L040" && row.trial === 3),
  );
}

let oneTrialLost: string | undefined;
const oneTrialLostPath = () => {
  oneTrialLost ??= changedRelease(withOneTrialLost);
  return oneTrialLost;
};

export default [
  {
    says: "gate.py exists",
    test: (folder) => existsSync(join(folder, "gate.py")),
    tryNext: "keep gate.py in this problem folder and edit it there",
  },
  {
    says: "the report has a case for every gate lease and critical field, each with 3 trials",
    test: (folder) => {
      const cases = harmlessCases(folder);
      const everyCaseHasThree = cases.every((oneCase) => trialsOf(oneCase)?.length === TRIALS);
      return cases.length > 0 && everyCaseHasThree && coversEveryGateCase(folder);
    },
    tryNext:
      'give each case "case" (the lease id), "field" and "trials": ' +
      "a list of 3 true or false values, one per trial row",
  },
  {
    says: "the trials are read from the release, in trial order",
    test: (folder) => {
      const flaky = findCase(folder, flakyLease(), "monthly_rent");
      return JSON.stringify(flaky?.trials) === JSON.stringify([true, false, true]);
    },
    tryNext:
      "sort the rows by trial and score each one; on clause-ids-in-answer, " +
      "L001 rent is right, wrong, right",
  },
  {
    says: "pass@3 and pass^3 match the trials of every case",
    test: (folder) => {
      const cases = harmlessCases(folder);
      return cases.length > 0 && cases.every(numbersMatch);
    },
    tryNext: "with p = right trials / 3, pass_at_3 is 1 - (1 - p) ** 3 and pass_hat_3 is p ** 3",
  },
  {
    says: "a case passes when it is right in at least 2 of its 3 trials",
    test: (folder) => {
      const cases = harmlessCases(folder);
      return cases.length > 0 && cases.every(passedMatchesShare);
    },
    tryNext: 'set "passed" to true when 2 or 3 trials are right, and false otherwise',
  },
  {
    says: "the flaky lease L001 does not block clause-ids-in-answer",
    test: (folder) => ships(runGate(folder, HARMLESS)),
    tryNext:
      "decide each case on the share of trials, not on every trial: " +
      "one wrong trial in three is noise",
  },
  {
    says: "the gate still blocks cheaper-model, which is wrong in every trial",
    test: (folder) => blocks(runGate(folder, "cheaper-model")),
    tryNext: "keep the critical-field rule from gate-the-release; only the trials are new",
  },
  {
    says: "the gate blocks when a case has fewer than 3 trials (it fails closed)",
    test: (folder) => blocks(runGate(folder, oneTrialLostPath())),
    tryNext: "count the trials of each case and block when one has fewer than 3",
  },
] satisfies Rule[];
