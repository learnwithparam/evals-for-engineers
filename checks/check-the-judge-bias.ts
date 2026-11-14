import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { type JsonRecord, readJsonl } from "./lib/world";

type Run = { pair: string; [field: string]: unknown };

const RATE_TOLERANCE = 0.005;
// The judge shows length bias when it picks the longer answer in this share of pairs or more.
const LENGTH_BIAS_AT = 0.7;

// Two lists hold the same ids when they match once both are sorted.
function sameIds(left: unknown[], right: unknown[]): boolean {
  const sortedLeft = [...left].sort();
  const sortedRight = [...right].sort();
  return JSON.stringify(sortedLeft) === JSON.stringify(sortedRight);
}

const runs = (folder: string) => readJsonl<Run>(join(folder, "judge_runs.jsonl"));

function report(folder: string): JsonRecord {
  const path = join(folder, "bias_report.json");
  return existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : {};
}

const flipped = (folder: string) =>
  runs(folder)
    .filter((run) => run.picked_original !== run.picked_swapped)
    .map((run) => run.pair);

function near(written: unknown, wanted: number): boolean {
  return typeof written === "number" && Math.abs(written - wanted) <= RATE_TOLERANCE;
}

export default [
  {
    says: "bias_report.json exists with the six fields",
    test: (folder) => {
      const written = report(folder);
      return [
        "flip_rate",
        "longer_pick_rate",
        "length_bias",
        "length_fix",
        "flipped_pairs",
        "fix",
      ].every((field) => field in written);
    },
    tryNext: "run uv run python bias_report.py; it writes bias_report.json for you",
  },
  {
    says: "flip_rate is the share of pairs where swapping the order changed the winner",
    test: (folder) => near(report(folder).flip_rate, flipped(folder).length / runs(folder).length),
    tryNext:
      "count the pairs where picked_original and picked_swapped differ, " +
      "not the pairs where they agree",
  },
  {
    says: "longer_pick_rate is the share of pairs where the judge picked the longer answer",
    test: (folder) => {
      const rows = runs(folder);
      const longerWins = rows.filter((run) => run.picked_original === run.longer).length;
      return near(report(folder).longer_pick_rate, longerWins / rows.length);
    },
    tryNext: "compare picked_original with longer on every pair, then divide by all the pairs",
  },
  {
    says: "length_bias says present when the judge picked the longer answer often enough",
    test: (folder) => {
      const rows = runs(folder);
      const longerWins = rows.filter((run) => run.picked_original === run.longer).length;
      const wanted = longerWins / rows.length >= LENGTH_BIAS_AT ? "present" : "absent";
      return report(folder).length_bias === wanted;
    },
    tryNext: "length_bias is present when the longer pick rate is 0.7 or more, otherwise absent",
  },
  {
    says: "length_fix says what you will do about length",
    test: (folder) => {
      const fix = String(report(folder).length_fix ?? "").toLowerCase();
      return fix.includes("length") && /same|equal|ignore|trim|shorten/.test(fix);
    },
    tryNext: "one sentence such as: match answer lengths, or tell the judge to ignore length",
  },
  {
    says: "flipped_pairs names every pair that flipped, and no other",
    test: (folder) => {
      const written = report(folder).flipped_pairs;
      if (!Array.isArray(written)) return false;
      return sameIds(written, flipped(folder));
    },
    tryNext: "list the pair ids where picked_original and picked_swapped are not the same answer",
  },
  {
    says: "fix says to swap the order and ask twice",
    test: (folder) => {
      const fix = String(report(folder).fix ?? "").toLowerCase();
      return fix.includes("swap") && (fix.includes("twice") || fix.includes("both"));
    },
    tryNext:
      "write one sentence such as: judge every pair twice with the order swapped, " +
      "and count a pair only when both orders agree",
  },
] satisfies Rule[];
