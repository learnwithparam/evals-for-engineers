import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { csvHeader, PLANTED_MODES, plantedIn, readCsv } from "./lib/world";

const fails = (d: string) =>
  readCsv(join(d, "marks.csv"))
    .filter((r) => r.mark === "fail")
    .map((r) => r.trace_id);
const notes = (d: string) =>
  new Map(readCsv(join(d, "notes.csv")).map((r) => [r.trace_id, r.note ?? ""]));
// Words that name a fix or a cause. A note describes what the trace did, never why or what to change.
const DIAGNOSIS =
  /\b(should|prompt|fix|needs? to|change the|add an?|instead|retrain|the model (forgot|didn't|did not))\b/i;
const words = (s: string) => s.split(/\s+/).filter(Boolean).length;

export default [
  {
    says: "notes.csv exists with the columns trace_id and note",
    test: (d) =>
      existsSync(join(d, "notes.csv")) &&
      csvHeader(join(d, "notes.csv")).join(",") === "trace_id,note",
    tryNext: "keep the header line trace_id,note and add one row per failed trace",
  },
  {
    says: "every trace marked fail has a note",
    test: (d) => fails(d).every((i) => (notes(d).get(i) ?? "").trim() !== ""),
    tryNext:
      "open uv run review note-the-failures; it shows only the failed traces and saves each note",
  },
  {
    says: "every note has at least 5 words",
    test: (d) => [...notes(d).values()].every((n) => words(n) >= 5),
    tryNext: "say which field is wrong, what the abstract says and what the lease says",
  },
  {
    says: "no note names a fix or a cause",
    test: (d) => [...notes(d).values()].every((n) => !DIAGNOSIS.test(n)),
    tryNext: "describe the behaviour, do not diagnose: drop words like should, prompt and fix",
  },
  {
    says: "each note on a planted fault names the field that went wrong",
    test: (d) =>
      plantedIn(fails(d)).every((p) => PLANTED_MODES[p.mode].words.test(notes(d).get(p.id) ?? "")),
    tryNext: "name the field in the note: rent, the rent step, or the renewal notice days",
  },
] satisfies Rule[];
