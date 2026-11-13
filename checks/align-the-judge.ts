import { existsSync } from "node:fs";
import { join } from "node:path";
import {
  danaLabels,
  deskTruth,
  idsIn,
  near,
  pairsFor,
  runJudge,
  tprTnr,
  verdictsById,
} from "../parts/03-judge-what-code-cannot/judge-check";
import type { Rule } from "../scripts/verify";
import { once } from "./lib/run";
import { readJson } from "./lib/world";

// The learner writes judge_dev.json, so every field may be missing or the wrong type.
type DevReport = {
  tpr?: unknown;
  tnr?: unknown;
  disagreements?: { id?: unknown }[];
  changes?: { trace_id?: unknown; change?: unknown }[];
};

const FAULTS_THE_DRAFT_MISSES = [3, 5];

// The check runs the learner's judge on dev itself, so the numbers never come from their report.
const devVerdicts = once((folder: string) => verdictsById(runJudge(folder, "dev"), idsIn("dev")));
const devScores = (folder: string) => {
  const verdicts = devVerdicts(folder);
  return verdicts ? tprTnr(pairsFor(verdicts)) : undefined;
};
const report = (folder: string) => readJson<DevReport>(join(folder, "judge_dev.json"));

/** Dev answers the judge gets wrong now: where its verdict and Dana's label differ. */
function disagreementIds(folder: string): string[] {
  const verdicts = devVerdicts(folder);
  if (!verdicts) return [];
  const dana = danaLabels();
  return [...verdicts.keys()].filter((id) => verdicts.get(id) !== dana.get(id));
}

/** Dev answers the first draft prompt passed and Dana failed: its missing rules. */
function draftMisses(): string[] {
  const truth = deskTruth();
  const dana = danaLabels();
  const failed = idsIn("dev").filter((id) => dana.get(id) === "fail");
  return failed.filter((id) => FAULTS_THE_DRAFT_MISSES.includes(Number(truth.get(id)?.fault)));
}

function namesARealDisagreement(folder: string): boolean {
  const known = new Set([...draftMisses(), ...disagreementIds(folder)]);
  const changes = report(folder).changes ?? [];
  const described = changes.filter((change) => String(change.change ?? "").trim().length > 10);
  return described.some((change) => known.has(String(change.trace_id)));
}

export default [
  {
    says: "judge_dev.json exists, written by align.py",
    test: (folder) => existsSync(join(folder, "judge_dev.json")),
    tryNext: "finish tpr_tnr() in align.py, then run uv run python align.py",
  },
  {
    says: "run.py answers all 50 dev cases with pass or fail",
    test: (folder) => devVerdicts(folder) !== undefined,
    tryNext:
      "run uv run python cases.py dev | uv run python run.py and read the error; " +
      "with no key, replay knows only recorded prompts",
  },
  {
    says: "the judge's TPR on dev is at least 0.80",
    test: (folder) => (devScores(folder)?.tpr ?? 0) >= 0.8,
    tryNext: "read the answers Dana passes that the judge fails, and say why they pass",
  },
  {
    says: "the judge's TNR on dev is at least 0.80",
    test: (folder) => (devScores(folder)?.tnr ?? 0) >= 0.8,
    tryNext:
      "read the answers Dana fails that the judge passes; " +
      'add the rule they break, such as dropping "not less than"',
  },
  {
    says: "the TPR and TNR in judge_dev.json match your judge's own verdicts",
    test: (folder) => {
      const scores = devScores(folder);
      const written = report(folder);
      return !!scores && near(written.tpr, scores.tpr) && near(written.tnr, scores.tnr);
    },
    tryNext: "write judge_dev.json with align.py after your last prompt change; never by hand",
  },
  {
    says: "judge_dev.json lists every disagreement",
    test: (folder) => {
      const listed = (report(folder).disagreements ?? []).map((item) => String(item.id));
      const expected = disagreementIds(folder);
      return listed.length === expected.length && expected.every((id) => listed.includes(id));
    },
    tryNext: "list each dev answer where the judge and Dana differ; run align.py again",
  },
  {
    says: "the change log names a disagreement it fixes",
    test: namesARealDisagreement,
    tryNext:
      "add a row to changes.csv: the trace_id of a disagreement and the rule you added for it",
  },
] satisfies Rule[];
