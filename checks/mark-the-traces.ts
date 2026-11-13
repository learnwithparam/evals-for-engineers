import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { csvHeader, danaAbstractor, plantedIn, readCsv, readJsonl } from "./lib/world";

const ids = (folder: string): string[] => {
  const sample = readJsonl(join(folder, "sample.jsonl"));
  return sample.map((trace) => trace.trace_id as string);
};
const marks = (folder: string) => {
  const rows = readCsv(join(folder, "marks.csv"));
  return new Map(rows.map((row) => [row.trace_id, row.mark?.toLowerCase()]));
};
const agreeWithDana = (folder: string) => {
  const dana = danaAbstractor();
  const learnerMarks = marks(folder);
  const agreed = ids(folder).filter((id) => learnerMarks.get(id) === dana.get(id)?.verdict);
  return agreed.length;
};

export default [
  {
    says: "marks.csv exists with the columns trace_id and mark",
    test: (folder) =>
      existsSync(join(folder, "marks.csv")) &&
      csvHeader(join(folder, "marks.csv")).join(",") === "trace_id,mark",
    tryNext:
      "start the review app with uv run review mark-the-traces, " +
      "or keep the header line trace_id,mark",
  },
  {
    says: "every trace in sample.jsonl has one mark, and no other trace has one",
    test: (folder) => {
      const rows = readCsv(join(folder, "marks.csv")).map((row) => row.trace_id);
      const want = ids(folder);
      return (
        rows.length === want.length &&
        new Set(rows).size === rows.length &&
        want.every((id) => rows.includes(id))
      );
    },
    tryNext: "go through all 40 traces in the review app; each trace gets exactly one row",
  },
  {
    says: "every mark is pass or fail, with no defer left",
    test: (folder) => {
      const everyMark = [...marks(folder).values()];
      return everyMark.every((mark) => mark === "pass" || mark === "fail");
    },
    tryNext: "come back to the traces you deferred and decide pass or fail on each",
  },
  {
    says: "every trace with a planted fault is marked fail",
    test: (folder) =>
      plantedIn(ids(folder)).every((planted) => marks(folder).get(planted.id) === "fail"),
    tryNext:
      "compare rent, rent steps and renewal notice days with the lease text, amendments included",
  },
  {
    says: "your marks agree with Dana's on at least 32 of the 40 traces",
    // 80% agreement: 32 of a 40-trace sample, and the same share of any other size.
    test: (folder) => agreeWithDana(folder) >= Math.ceil(0.8 * ids(folder).length),
    tryNext:
      "a trace fails when any field differs from the signed lease; " +
      "check every field, not only rent",
  },
] satisfies Rule[];
