import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { csvHeader, PLANTED_MODES, plantedIn, readCsv } from "./lib/world";

const failedIds = (folder: string) => {
  const rows = readCsv(join(folder, "marks.csv"));
  const failed = rows.filter((row) => row.mark === "fail");
  return failed.map((row) => row.trace_id);
};
const notes = (folder: string) => {
  const rows = readCsv(join(folder, "notes.csv"));
  return new Map(rows.map((row) => [row.trace_id, row.note ?? ""]));
};
const everyNote = (folder: string) => [...notes(folder).values()];

// Words that name a fix or a cause.
// A note describes what the trace did, never why or what to change.
const DIAGNOSIS_WORDS = [
  "should",
  "prompt",
  "fix",
  "needs? to",
  "change the",
  "add an?",
  "instead",
  "retrain",
  "the model (forgot|didn't|did not)",
];
const DIAGNOSIS = new RegExp(`\\b(${DIAGNOSIS_WORDS.join("|")})\\b`, "i");
const wordCount = (text: string) => text.split(/\s+/).filter(Boolean).length;

export default [
  {
    says: "notes.csv exists with the columns trace_id and note",
    test: (folder) =>
      existsSync(join(folder, "notes.csv")) &&
      csvHeader(join(folder, "notes.csv")).join(",") === "trace_id,note",
    tryNext: "keep the header line trace_id,note and add one row per failed trace",
  },
  {
    says: "every trace marked fail has a note",
    test: (folder) => failedIds(folder).every((id) => (notes(folder).get(id) ?? "").trim() !== ""),
    tryNext:
      "open uv run review note-the-failures; it shows only the failed traces and saves each note",
  },
  {
    says: "every note has at least 5 words",
    test: (folder) => everyNote(folder).every((note) => wordCount(note) >= 5),
    tryNext: "say which field is wrong, what the abstract says and what the lease says",
  },
  {
    says: "no note names a fix or a cause",
    test: (folder) => everyNote(folder).every((note) => !DIAGNOSIS.test(note)),
    tryNext: "describe the behaviour, do not diagnose: drop words like should, prompt and fix",
  },
  {
    says: "each note on a planted fault names the field that went wrong",
    test: (folder) =>
      plantedIn(failedIds(folder)).every((planted) => {
        const note = notes(folder).get(planted.id) ?? "";
        return PLANTED_MODES[planted.mode].words.test(note);
      }),
    tryNext: "name the field in the note: rent, the rent step, or the renewal notice days",
  },
] satisfies Rule[];
