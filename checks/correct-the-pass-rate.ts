import { existsSync } from "node:fs";
import { join } from "node:path";
import {
  idsIn,
  near,
  runJudge,
  verdictsById,
} from "../parts/03-judge-what-code-cannot/judge-check";
import type { Rule } from "../scripts/verify";
import { once } from "./lib/run";
import { readJson } from "./lib/world";

// The learner writes both files, so every field may be missing or the wrong type.
type RateReport = {
  n?: unknown;
  [field: string]: unknown;
  tpr?: unknown;
  tnr?: unknown;
  corrected?: unknown;
};
type TestReport = { tpr?: unknown; tnr?: unknown };

const rate = (folder: string) => readJson<RateReport>(join(folder, "grounded_rate.json"));
const testRun = (folder: string) => readJson<TestReport>(join(folder, "judge_test.json"));

// The check judges the 200 unlabelled answers itself, so the raw rate never comes from the file.
const rawRate = once((folder: string): number | undefined => {
  const ids = idsIn("unlabelled");
  const verdicts = verdictsById(runJudge(folder, "unlabelled"), ids);
  if (!verdicts) return undefined;
  const passes = [...verdicts.values()].filter((verdict) => verdict === "pass").length;
  return passes / ids.length;
});

/** (raw + TNR - 1) / (TPR + TNR - 1), kept between 0 and 1. */
function correctedRate(raw: number, tpr: number, tnr: number): number {
  const estimate = (raw + tnr - 1) / (tpr + tnr - 1);
  return Math.min(1, Math.max(0, estimate));
}

function matchesTheFormula(folder: string): boolean {
  const raw = rawRate(folder);
  const test = testRun(folder);
  if (raw === undefined || typeof test.tpr !== "number" || typeof test.tnr !== "number") {
    return false;
  }
  return near(rate(folder).corrected, correctedRate(raw, test.tpr, test.tnr));
}

export default [
  {
    says: "grounded_rate.json exists, written by rate.py",
    test: (folder) => existsSync(join(folder, "grounded_rate.json")),
    tryNext: "finish corrected() in rate.py, then run uv run python rate.py",
  },
  {
    says: "it covers the 200 unlabelled answers",
    test: (folder) => rate(folder).n === idsIn("unlabelled").length,
    tryNext: "judge every lease desk answer Dana did not label: cases.py unlabelled gives 200",
  },
  {
    says: "the raw rate matches your judge's verdicts on those answers",
    test: (folder) => {
      const raw = rawRate(folder);
      return raw !== undefined && near(rate(folder).raw_rate, raw);
    },
    tryNext: "raw_rate is the share of the 200 answers your judge passes, before any correction",
  },
  {
    says: "TPR and TNR are the ones judge_test.json measured",
    test: (folder) => {
      const written = rate(folder);
      const test = testRun(folder);
      return written.tpr === test.tpr && written.tnr === test.tnr;
    },
    tryNext: "read TPR and TNR from judge_test.json; never from dev, and never swapped",
  },
  {
    says: "the corrected rate matches (raw + TNR - 1) / (TPR + TNR - 1) within 0.01",
    test: matchesTheFormula,
    tryNext:
      "the judge passes some bad answers and fails some good ones; " +
      "use TNR in the top line and TPR + TNR - 1 below",
  },
  {
    says: "the 95% interval holds the corrected rate",
    test: (folder) => {
      const written = rate(folder);
      const { corrected, ci_low: low, ci_high: high } = written;
      const numbers = [corrected, low, high].every((value) => typeof value === "number");
      return numbers && Number(low) <= Number(corrected) && Number(corrected) <= Number(high);
    },
    tryNext: "write ci_low and ci_high from a bootstrap, so ci_low <= corrected <= ci_high",
  },
] satisfies Rule[];
