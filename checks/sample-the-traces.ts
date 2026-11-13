import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { once, runPython } from "./lib/run";
import { abstractorTraces, type Trace } from "./lib/world";

// Run the learner's sampler into a temp folder, never over their own sample.jsonl.
const draw = (folder: string, seed: number) => {
  const scratch = mkdtempSync(join(tmpdir(), "sample-"));
  const out = join(scratch, "sample.jsonl");
  const ran = runPython("sample.py", ["--seed", String(seed), "--out", out], folder);
  if (ran.code !== 0 || !existsSync(out)) return null;
  const lines = readFileSync(out, "utf8").split("\n");
  const filled = lines.filter((line) => line.trim());
  return filled.map((line) => JSON.parse(line).trace_id as string);
};
const first = once((folder) => draw(folder, 7));
const again = once((folder) => draw(folder, 7));
const other = once((folder) => draw(folder, 8));
const traces = () => abstractorTraces();

function count(ids: string[] | null, matches: (trace: Trace) => boolean): number {
  const known = (ids ?? []).filter((id) => traces().has(id));
  return known.filter((id) => matches(traces().get(id) as Trace)).length;
}

function idsAreRealAndUnique(folder: string): boolean {
  const ids = first(folder);
  if (!ids) return false;
  return new Set(ids).size === ids.length && ids.every((id) => traces().has(id));
}

export default [
  {
    says: "sample.py exists",
    test: (folder) => existsSync(join(folder, "sample.py")),
    tryNext: "keep sample.py in this problem folder and edit it there",
  },
  {
    says: "sample.py --seed 7 runs and writes 40 traces",
    test: (folder) => first(folder)?.length === 40,
    tryNext:
      "run uv run python sample.py --seed 7 and read the error; " +
      "sample() must return a list of 40 traces",
  },
  {
    says: "every trace id is real and none repeats",
    test: idsAreRealAndUnique,
    tryNext:
      "write whole trace lines from world/data/traces/abstractor.jsonl " +
      "and never pick the same trace twice",
  },
  {
    says: "at least 8 traces of amended leases",
    test: (folder) => count(first(folder), (trace) => trace.amendments > 0) >= 8,
    tryNext: "pick traces where amendments is above 0 first, then fill the rest",
  },
  {
    says: "at least 3 traces of commercial leases",
    test: (folder) => count(first(folder), (trace) => trace.lease_type === "commercial") >= 3,
    tryNext:
      "pick commercial leases as their own group first; " +
      "a random draw often misses the 10 shop leases",
  },
  {
    says: "the same seed gives the same sample",
    test: (folder) =>
      !!first(folder) && JSON.stringify(first(folder)) === JSON.stringify(again(folder)),
    tryNext:
      "make one random.Random(seed) and draw every pick from it, then sort the result by trace_id",
  },
  {
    says: "a different seed gives a different sample",
    test: (folder) =>
      !!first(folder) &&
      !!other(folder) &&
      JSON.stringify(first(folder)) !== JSON.stringify(other(folder)),
    tryNext: "draw with the seed you are given; a fixed list of ids is not a sample",
  },
] satisfies Rule[];
