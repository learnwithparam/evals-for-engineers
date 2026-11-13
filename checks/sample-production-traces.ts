import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  BATCHES,
  batchIds,
  productionTruth,
} from "../parts/05-watch-production/helpers/production";
import type { Rule } from "../scripts/verify";
import { once, runPython } from "./lib/run";

// One line of the learner's verdicts.jsonl. They wrote it, so any field may be missing.
type VerdictRow = Record<string, unknown>;

// Run the learner's monitor into a temp folder, never over their own verdicts.jsonl.
function monitorRun(folder: string, seed: number): VerdictRow[] | null {
  const scratch = mkdtempSync(join(tmpdir(), "monitor-"));
  const out = join(scratch, "verdicts.jsonl");
  const ran = runPython("monitor.py", ["--seed", String(seed), "--out", out], folder, 120_000);
  if (ran.code !== 0 || !existsSync(out)) return null;
  const lines = readFileSync(out, "utf8").split("\n");
  const filled = lines.filter((line) => line.trim());
  return filled.map((line) => JSON.parse(line));
}

const first = once((folder) => monitorRun(folder, 7));
const again = once((folder) => monitorRun(folder, 7));
const other = once((folder) => monitorRun(folder, 8));

const idsOf = (rows: VerdictRow[] | null) => (rows ?? []).map((row) => String(row.trace_id));

function sampledIn(folder: string, batch: number): string[] {
  const inBatch = new Set(batchIds(batch));
  return idsOf(first(folder)).filter((id) => inBatch.has(id));
}

function idsAreRealAndUnique(folder: string): boolean {
  const rows = first(folder);
  if (!rows || rows.length === 0) return false;
  const ids = idsOf(rows);
  const truth = productionTruth();
  const unique = new Set(ids).size === ids.length;
  const batchesRight = rows.every((row) => truth.get(String(row.trace_id))?.batch === row.batch);
  return unique && batchesRight;
}

function everyBuildingSampled(folder: string): boolean {
  const truth = productionTruth();
  return BATCHES.every((batch) => {
    const buildingsInBatch = new Set(batchIds(batch).map((id) => truth.get(id)?.building));
    const sampled = new Set(sampledIn(folder, batch).map((id) => truth.get(id)?.building));
    return [...buildingsInBatch].every((building) => sampled.has(building));
  });
}

function everyNewTemplateTraceSampled(folder: string): boolean {
  const truth = productionTruth();
  const sampled = new Set(idsOf(first(folder)));
  const newTraces = [...truth].filter(([, trace]) => trace.unseen);
  return newTraces.length > 0 && newTraces.every(([id]) => sampled.has(id));
}

function verdictsMatchTheJudge(folder: string): boolean {
  const rows = first(folder);
  if (!rows || rows.length === 0) return false;
  const truth = productionTruth();
  return rows.every((row) => truth.get(String(row.trace_id))?.verdict === row.verdict);
}

const sameIds = (left: VerdictRow[] | null, right: VerdictRow[] | null) =>
  JSON.stringify(idsOf(left)) === JSON.stringify(idsOf(right));

export default [
  {
    says: "monitor.py exists",
    test: (folder) => existsSync(join(folder, "monitor.py")),
    tryNext: "keep monitor.py in this problem folder and edit it there",
  },
  {
    says: "monitor.py --seed 7 runs and grades at least 30 traces in every batch",
    test: (folder) => BATCHES.every((batch) => sampledIn(folder, batch).length >= 30),
    tryNext:
      "run uv run python monitor.py --seed 7 and read the error; " +
      "sample_batch() must return at least 30 traces for each of the 7 batches",
  },
  {
    says: "every trace id is real, none repeats, and each sits in its own batch",
    test: idsAreRealAndUnique,
    tryNext: "write each trace once, with the batch number the trace itself carries",
  },
  {
    says: "every building in a batch has at least one trace in the sample",
    test: everyBuildingSampled,
    tryNext:
      "after the new-template traces, add one trace from each building that has none yet, " +
      "then fill the rest at random",
  },
  {
    says: "every trace on a template the golden set lacks is in the sample",
    test: everyNewTemplateTraceSampled,
    tryNext:
      'take every trace where trace["new_template"] is True first; ' +
      "a random draw leaves some of them out",
  },
  {
    says: "every verdict is the aligned grounded judge's verdict",
    test: verdictsMatchTheJudge,
    tryNext:
      "grade each trace with judge.judge(question, answer, cited_clauses(trace)); " +
      "a rule of your own is not the judge Dana aligned",
  },
  {
    says: "the same seed gives the same sample",
    test: (folder) => !!first(folder) && sameIds(first(folder), again(folder)),
    tryNext: "draw every pick from the one random_generator that monitor() makes from the seed",
  },
  {
    says: "a different seed gives a different sample",
    test: (folder) => !!first(folder) && !!other(folder) && !sameIds(first(folder), other(folder)),
    tryNext:
      "draw with the random_generator you are given; the first traces of a batch are not a sample",
  },
] satisfies Rule[];
