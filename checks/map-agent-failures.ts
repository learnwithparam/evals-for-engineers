import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { helperOutput } from "../parts/06-evaluate-retrieval-and-agent/helpers/truth";
import type { Rule } from "../scripts/verify";
import { csvHeader, readCsv } from "./lib/world";

const COLUMNS = ["last_good", "first_failed", "count"];
const STATES = [
  "start",
  "get_abstract",
  "search_lease",
  "get_ledger",
  "propose_charge",
  "draft_notice",
];

type Failures = { failed: string[]; traces: number; cells: Record<string, number> };

const failures = () => helperOutput<Failures>("agent_failures.py");
const transitionsFile = (folder: string) => join(folder, "transitions.csv");
const rows = (folder: string) => readCsv(transitionsFile(folder));
const cellKey = (row: Record<string, string>) => `${row.last_good}/${row.first_failed}`;

function topCell(): string {
  const cells = Object.entries(failures().cells);
  cells.sort((left, right) => right[1] - left[1]);
  return cells[0][0];
}

function everyCellMatches(folder: string): boolean {
  const written = new Map(rows(folder).map((row) => [cellKey(row), Number(row.count)]));
  const wanted = Object.entries(failures().cells);
  return (
    written.size === wanted.length && wanted.every(([key, count]) => written.get(key) === count)
  );
}

function nextFixNamesTheTopCell(folder: string): boolean {
  const nextFixFile = join(folder, "next_fix.txt");
  if (!existsSync(nextFixFile)) return false;
  const text = readFileSync(nextFixFile, "utf8");
  const [lastGood, firstFailed] = topCell().split("/");
  return text.includes(`${lastGood} -> ${firstFailed}`);
}

export default [
  {
    says: "transitions.csv has the columns last_good, first_failed and count",
    test: (folder) =>
      existsSync(transitionsFile(folder)) &&
      JSON.stringify(csvHeader(transitionsFile(folder))) === JSON.stringify(COLUMNS),
    tryNext: "run uv run python map_failures.py; it writes transitions.csv for you",
  },
  {
    says: "every cell uses the shared state names",
    test: (folder) =>
      rows(folder).length > 0 &&
      rows(folder).every(
        (row) => STATES.includes(row.last_good) && STATES.includes(row.first_failed),
      ),
    tryNext:
      "use the planned states in PLAN, or start; post_charge is never planned, " +
      "so a run that calls it fails at propose_charge",
  },
  {
    says: "the counts add up to the 13 runs that failed, not to all 80",
    test: (folder) => {
      const total = rows(folder).reduce((sum, row) => sum + Number(row.count), 0);
      return total === failures().failed.length;
    },
    tryNext: "return None from first_failure() for a run whose every planned step went right",
  },
  {
    says: "every cell has the right count",
    test: everyCellMatches,
    tryNext:
      "walk the plan from the start and stop at the first wrong step; " +
      "check the lease id and the amount, not only the tool name",
  },
  {
    says: "next_fix.txt names the top cell as the next fix",
    test: nextFixNamesTheTopCell,
    tryNext: "write the cell with the highest count, as last_good -> first_failed",
  },
] satisfies Rule[];
