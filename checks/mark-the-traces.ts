import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { csvHeader, danaAbstractor, plantedIn, readCsv, readJsonl } from "./lib/world";

const ids = (d: string): string[] => readJsonl(join(d, "sample.jsonl")).map((t) => t.trace_id);
const marks = (d: string) =>
  new Map(readCsv(join(d, "marks.csv")).map((r) => [r.trace_id, r.mark?.toLowerCase()]));
const agree = (d: string) => {
  const dana = danaAbstractor(),
    m = marks(d);
  return ids(d).filter((i) => m.get(i) === dana.get(i)?.verdict).length;
};

export default [
  {
    says: "marks.csv exists with the columns trace_id and mark",
    test: (d) =>
      existsSync(join(d, "marks.csv")) &&
      csvHeader(join(d, "marks.csv")).join(",") === "trace_id,mark",
    tryNext:
      "start the review app with uv run review mark-the-traces, or keep the header line trace_id,mark",
  },
  {
    says: "every trace in sample.jsonl has one mark, and no other trace has one",
    test: (d) => {
      const rows = readCsv(join(d, "marks.csv")).map((r) => r.trace_id);
      const want = ids(d);
      return (
        rows.length === want.length &&
        new Set(rows).size === rows.length &&
        want.every((i) => rows.includes(i))
      );
    },
    tryNext: "go through all 40 traces in the review app; each trace gets exactly one row",
  },
  {
    says: "every mark is pass or fail, with no defer left",
    test: (d) => [...marks(d).values()].every((m) => m === "pass" || m === "fail"),
    tryNext: "come back to the traces you deferred and decide pass or fail on each",
  },
  {
    says: "every trace with a planted fault is marked fail",
    test: (d) => plantedIn(ids(d)).every((p) => marks(d).get(p.id) === "fail"),
    tryNext:
      "compare rent, rent steps and renewal notice days with the lease text, amendments included",
  },
  {
    says: "your marks agree with Dana's on at least 32 of the 40 traces",
    test: (d) => agree(d) >= Math.ceil(0.8 * ids(d).length),
    tryNext:
      "a trace fails when any field differs from the signed lease; check every field, not only rent",
  },
] satisfies Rule[];
