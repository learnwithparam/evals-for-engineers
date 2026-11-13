import { existsSync } from "node:fs";
import { join } from "node:path";
import { danaLabels, judgeInputs, near } from "../parts/03-judge-what-code-cannot/judge-check";
import type { Rule } from "../scripts/verify";
import { readCsv, readJson } from "./lib/world";

// The learner writes agreement.json, so every field may be missing or the wrong type.
type Agreement = { n?: unknown; agreed?: unknown; kappa?: unknown };

/** The 30 answers to label: all 20 train answers, then the first 5 passes and 5 fails in dev. */
function answerIds(): string[] {
  const dana = danaLabels();
  const devIds = judgeInputs("dev").map((input) => input.id);
  const devPasses = devIds.filter((id) => dana.get(id) === "pass").slice(0, 5);
  const devFails = devIds.filter((id) => dana.get(id) === "fail").slice(0, 5);
  const trainIds = judgeInputs("train").map((input) => input.id);
  return [...trainIds, ...devPasses, ...devFails].sort();
}

const labels = (folder: string) => readCsv(join(folder, "labels.csv"));
const agreement = (folder: string) => readJson<Agreement>(join(folder, "agreement.json"));

function labelFor(folder: string): Map<string, string> {
  const rows = labels(folder);
  return new Map(rows.map((row) => [row.trace_id, row.label.toLowerCase()]));
}

/** Cohen's kappa between the learner and Dana, recomputed from labels.csv. */
function kappa(folder: string): number {
  const mine = labelFor(folder);
  const dana = danaLabels();
  const ids = answerIds();
  const agreed = ids.filter((id) => mine.get(id) === dana.get(id)).length;
  const observed = agreed / ids.length;
  let chance = 0;
  for (const label of ["pass", "fail"]) {
    const myShare = ids.filter((id) => mine.get(id) === label).length / ids.length;
    const herShare = ids.filter((id) => dana.get(id) === label).length / ids.length;
    chance += myShare * herShare;
  }
  if (chance === 1) return 1;
  return (observed - chance) / (1 - chance);
}

const wordCount = (text: string) => text.split(/\s+/).filter(Boolean).length;

export default [
  {
    says: "labels.csv labels all 30 answers in answers.jsonl, once each",
    test: (folder) => {
      const rows = labels(folder);
      const ids = answerIds();
      const labelled = new Set(rows.map((row) => row.trace_id));
      return rows.length === ids.length && ids.every((id) => labelled.has(id));
    },
    tryNext: "add one row per answer to labels.csv: trace_id,label,critique",
  },
  {
    says: 'every label is "pass" or "fail"',
    test: (folder) => {
      const allLabels = [...labelFor(folder).values()];
      return allLabels.every((label) => /^(pass|fail)$/.test(label));
    },
    tryNext: 'write pass if the cited clauses support every claim, and fail if not; no "maybe"',
  },
  {
    says: "every label has a critique of 5 words or more",
    test: (folder) => {
      const rows = labels(folder);
      return rows.length > 0 && rows.every((row) => wordCount(row.critique ?? "") >= 5);
    },
    tryNext: "say in one sentence why the answer passes or fails, for example which words differ",
  },
  {
    says: "agreement.json exists, written by kappa.py",
    test: (folder) => existsSync(join(folder, "agreement.json")),
    tryNext: "finish cohens_kappa() in kappa.py, then run uv run python kappa.py",
  },
  {
    says: "the kappa in agreement.json matches your labels and Dana's",
    test: (folder) => {
      const written = agreement(folder);
      return written.n === answerIds().length && near(written.kappa, kappa(folder));
    },
    tryNext: "compute kappa from labels.csv with kappa.py; do not type the number in",
  },
] satisfies Rule[];
