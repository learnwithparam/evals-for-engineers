import { existsSync } from "node:fs";
import { join } from "node:path";
import { BATCHES, productionTruth } from "../parts/05-watch-production/helpers/production";
import type { Rule } from "../scripts/verify";
import { csvHeader, readCsv, readJsonl } from "./lib/world";

const COLUMNS = ["batch", "slice", "n", "raw_rate", "corrected_rate", "ci_low", "ci_high", "alert"];
const ALERT_FLOOR = 0.75;
const TOLERANCE = 0.01;
const NEW_BATCH = 5;

type ReportRow = Record<string, string>;
type Expected = { n: number; raw: number; corrected: number };

const batchesFile = (folder: string) => join(folder, "batches.csv");
const reportRows = (folder: string): ReportRow[] => readCsv(batchesFile(folder));
const rowKey = (batch: number | string, slice: string) => `${batch}/${slice}`;

/** TPR and TNR of the judge on Dana's held-out labels. Pass is the positive class. */
function judgeRates(folder: string): { tpr: number; tnr: number } {
  const pairs = readCsv(join(folder, "judge_test.csv"));
  const humanPasses = pairs.filter((pair) => pair.label === "pass");
  const humanFails = pairs.filter((pair) => pair.label === "fail");
  const agreedOnPasses = humanPasses.filter((pair) => pair.verdict === "pass").length;
  const agreedOnFails = humanFails.filter((pair) => pair.verdict === "fail").length;
  return { tpr: agreedOnPasses / humanPasses.length, tnr: agreedOnFails / humanFails.length };
}

/** The corrected rate, as stats.corrected() in the finished system computes it. */
function correct(raw: number, rates: { tpr: number; tnr: number }): number {
  const estimate = (raw + rates.tnr - 1) / (rates.tpr + rates.tnr - 1);
  return Math.min(1, Math.max(0, estimate));
}

function addVerdict(groups: Map<string, string[]>, key: string, verdict: string) {
  const group = groups.get(key) ?? [];
  group.push(verdict);
  groups.set(key, group);
}

/** What every row of batches.csv should say, recomputed from the folder's own verdicts.jsonl. */
function expectedRows(folder: string): Map<string, Expected> {
  const truth = productionTruth();
  const groups = new Map<string, string[]>();
  for (const row of readJsonl(join(folder, "verdicts.jsonl"))) {
    const verdict = String(row.verdict);
    addVerdict(groups, rowKey(Number(row.batch), "all"), verdict);
    const unseen = truth.get(String(row.trace_id))?.unseen;
    if (unseen) addVerdict(groups, rowKey(Number(row.batch), "new-template"), verdict);
  }
  const rates = judgeRates(folder);
  const expected = new Map<string, Expected>();
  for (const [key, verdicts] of groups) {
    const raw = verdicts.filter((verdict) => verdict === "pass").length / verdicts.length;
    expected.set(key, { n: verdicts.length, raw, corrected: correct(raw, rates) });
  }
  return expected;
}

const close = (written: string, wanted: number) => Math.abs(Number(written) - wanted) <= TOLERANCE;

function rowsMatch(folder: string, matches: (row: ReportRow, wanted: Expected) => boolean) {
  const expected = expectedRows(folder);
  const rows = reportRows(folder);
  return (
    rows.length > 0 &&
    rows.every((row) => {
      const wanted = expected.get(rowKey(row.batch, row.slice));
      return wanted !== undefined && matches(row, wanted);
    })
  );
}

function everyGroupHasItsRow(folder: string): boolean {
  const written = new Set(reportRows(folder).map((row) => rowKey(row.batch, row.slice)));
  const expected = [...expectedRows(folder).keys()];
  const allRows = BATCHES.every((batch) => written.has(rowKey(batch, "all")));
  return allRows && expected.every((key) => written.has(key));
}

function intervalHolds(row: ReportRow): boolean {
  const low = Number(row.ci_low);
  const high = Number(row.ci_high);
  const corrected = Number(row.corrected_rate);
  return low >= 0 && high <= 1 && low < high && low <= corrected && corrected <= high;
}

function alertFollowsTheRule(row: ReportRow, wanted: Expected): boolean {
  const shouldAlert = row.slice === "new-template" && wanted.corrected < ALERT_FLOOR;
  return row.alert === (shouldAlert ? "yes" : "no");
}

const alertingBatches = (folder: string) =>
  reportRows(folder)
    .filter((row) => row.alert === "yes")
    .map((row) => Number(row.batch));

export default [
  {
    says: "batches.csv exists with the columns batch, slice, n, raw_rate, ... alert",
    test: (folder) =>
      existsSync(batchesFile(folder)) &&
      JSON.stringify(csvHeader(batchesFile(folder))) === JSON.stringify(COLUMNS),
    tryNext: "run uv run python report.py; it writes batches.csv with the COLUMNS it names",
  },
  {
    says: "one all row per batch, and a new-template row where the batch has such traces",
    test: everyGroupHasItsRow,
    tryNext:
      "for each batch, write one row for every verdict, then one row for the verdicts " +
      "whose template the golden set lacks",
  },
  {
    says: "n and raw_rate match verdicts.jsonl on every row",
    test: (folder) =>
      rowsMatch(
        folder,
        (row, wanted) => Number(row.n) === wanted.n && close(row.raw_rate, wanted.raw),
      ),
    tryNext: 'raw_rate is the count of "pass" verdicts divided by n, the size of that group',
  },
  {
    says: "corrected_rate matches the correction with the judge's TPR and TNR",
    test: (folder) =>
      rowsMatch(folder, (row, wanted) => close(row.corrected_rate, wanted.corrected)),
    tryNext:
      "get tpr and tnr from stats.tpr_tnr(test_pairs), then call " +
      "stats.corrected(raw_rate, tpr, tnr); the raw rate still holds the judge's errors",
  },
  {
    says: "every interval holds its corrected rate and lies between 0 and 1",
    test: (folder) => rowsMatch(folder, (row) => intervalHolds(row)),
    tryNext: "take ci_low and ci_high from stats.bootstrap(test_pairs, verdicts) for that row",
  },
  {
    says: "alert is yes exactly on new-template rows below 0.75",
    test: (folder) => rowsMatch(folder, alertFollowsTheRule),
    tryNext:
      "should_alert() is True only when the slice is new-template " +
      "and corrected_rate is below ALERT_FLOOR",
  },
  {
    says: "the alert fires on batch 5, and on no batch before it",
    test: (folder) => {
      const batches = alertingBatches(folder);
      return batches.includes(NEW_BATCH) && batches.every((batch) => batch >= NEW_BATCH);
    },
    tryNext:
      "the known templates sit near 0.75 too; " +
      "alert on the new-template slice, which CI cannot test",
  },
] satisfies Rule[];
