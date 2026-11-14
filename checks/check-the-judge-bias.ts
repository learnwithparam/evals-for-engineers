import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { type JsonRecord, readJsonl } from "./lib/world";

type Run = { pair: string; picked_original: string; picked_swapped: string; longer: string };

const RATE_TOLERANCE = 0.005;

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
    says: "bias_report.json exists with the four fields",
    test: (folder) => {
      const written = report(folder);
      return ["flip_rate", "longer_pick_rate", "flipped_pairs", "fix"].every(
        (field) => field in written,
      );
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
    says: "flipped_pairs names every pair that flipped, and no other",
    test: (folder) => {
      const written = report(folder).flipped_pairs;
      if (!Array.isArray(written)) return false;
      return JSON.stringify([...written].sort()) === JSON.stringify([...flipped(folder)].sort());
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
