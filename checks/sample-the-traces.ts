import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { once, runPython } from "./lib/run";
import { abstractorTraces } from "./lib/world";

// Run the learner's sampler into a temp folder, never over their own sample.jsonl.
const draw = (dir: string, seed: number) => {
  const out = join(mkdtempSync(join(tmpdir(), "sample-")), "sample.jsonl");
  const r = runPython("sample.py", ["--seed", String(seed), "--out", out], dir);
  if (r.code !== 0 || !existsSync(out)) return null;
  return readFileSync(out, "utf8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l).trace_id as string);
};
const first = once((d) => draw(d, 7));
const again = once((d) => draw(d, 7));
const other = once((d) => draw(d, 8));
const traces = () => abstractorTraces();
const count = (ids: string[] | null, f: (t: any) => boolean) =>
  (ids ?? []).filter((id) => traces().has(id) && f(traces().get(id))).length;

export default [
  {
    says: "sample.py exists",
    test: (d) => existsSync(join(d, "sample.py")),
    tryNext: "keep sample.py in this problem folder and edit it there",
  },
  {
    says: "sample.py --seed 7 runs and writes 40 traces",
    test: (d) => first(d)?.length === 40,
    tryNext:
      "run uv run python sample.py --seed 7 and read the error; sample() must return a list of 40 traces",
  },
  {
    says: "every trace id is real and none repeats",
    test: (d) =>
      !!first(d) &&
      new Set(first(d)).size === first(d)!.length &&
      first(d)!.every((id) => traces().has(id)),
    tryNext:
      "write whole trace lines from world/data/traces/abstractor.jsonl and never pick the same trace twice",
  },
  {
    says: "at least 8 traces of amended leases",
    test: (d) => count(first(d), (t) => t.amendments > 0) >= 8,
    tryNext: "pick traces where amendments is above 0 first, then fill the rest",
  },
  {
    says: "at least 3 traces of commercial leases",
    test: (d) => count(first(d), (t) => t.lease_type === "commercial") >= 3,
    tryNext:
      "add a stratum for lease_type commercial; a random draw often misses the 10 shop leases",
  },
  {
    says: "the same seed gives the same sample",
    test: (d) => !!first(d) && JSON.stringify(first(d)) === JSON.stringify(again(d)),
    tryNext:
      "make one random.Random(seed) and draw every pick from it, then sort the result by trace_id",
  },
  {
    says: "a different seed gives a different sample",
    test: (d) => !!first(d) && !!other(d) && JSON.stringify(first(d)) !== JSON.stringify(other(d)),
    tryNext: "draw with the seed you are given; a fixed list of ids is not a sample",
  },
] satisfies Rule[];
