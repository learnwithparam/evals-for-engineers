import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { DATA, readJsonl } from "./lib/world";

// The learner writes every file here, so each field may be missing or the wrong type.
type TraceRow = { id?: unknown; input?: unknown; output?: unknown };
type ScoreRow = { id?: unknown; verdict?: unknown; reason?: unknown };

const MINIMUM_TRACES = 10;

// Two lists hold the same ids when they match once both are sorted.
function sameIds(left: unknown[], right: unknown[]): boolean {
  const sortedLeft = [...left].sort();
  const sortedRight = [...right].sort();
  return JSON.stringify(sortedLeft) === JSON.stringify(sortedRight);
}
const COURSE_WORLD = /fernhill|dana mensah|\bL\d{3}(-c\d+)?\b|\bdesk-\d{4}\b/i;

const read = (folder: string, name: string) => {
  const path = join(folder, name);
  return existsSync(path) ? readFileSync(path, "utf8") : "";
};

function rows<Shape>(folder: string, name: string): Shape[] {
  const path = join(folder, name);
  return existsSync(path) ? readJsonl<Shape>(path) : [];
}

const traces = (folder: string) => rows<TraceRow>(folder, "my_traces.jsonl");
const scores = (folder: string) => rows<ScoreRow>(folder, "my_scores.jsonl");
const text = (value: unknown) => (typeof value === "string" ? value.trim() : "");

export default [
  {
    says: "my_traces.jsonl holds at least 10 of your own traces with an id, input and output",
    test: (folder) => {
      const found = traces(folder);
      const whole = found.every((row) => text(row.id) && text(row.input) && text(row.output));
      const unique = new Set(found.map((row) => row.id)).size === found.length;
      const filled = found.every((row) => !text(row.id).startsWith("example"));
      return found.length >= MINIMUM_TRACES && whole && unique && filled;
    },
    tryNext: "replace the two example rows with 10 or more real traces from your system",
  },
  {
    says: "the traces are yours, not the course world",
    test: (folder) => {
      const found = traces(folder);
      const staff = new Set(
        readJsonl<{ question: string }>(join(DATA, "questions.jsonl")).map((row) => row.question),
      );
      const own = found.every(
        (row) => !COURSE_WORLD.test(JSON.stringify(row)) && !staff.has(text(row.input)),
      );
      return found.length > 0 && own;
    },
    tryNext:
      "export traces from your own system; the Fernhill traces and lease ids are for practice",
  },
  {
    says: "judge.txt names one criterion and asks for pass or fail",
    test: (folder) => {
      const judge = read(folder, "judge.txt");
      const first = judge.split("\n")[0] ?? "";
      const named = /^Criterion:/.test(first) && first.split(/\s+/).length >= 6;
      const answers = /\bpass\b/i.test(judge) && /\bfail\b/i.test(judge);
      return named && answers && !judge.includes("TODO");
    },
    tryNext:
      "start the first line with Criterion:, write one thing to check, then ask for pass or fail",
  },
  {
    says: "my_task.py loads your traces, uses judge.txt and scores the verdict",
    test: (folder) => {
      const task = read(folder, "my_task.py");
      const needs = [
        "inspect_ai",
        "json_dataset",
        "my_traces.jsonl",
        "judge.txt",
        "generate(",
        "@scorer",
      ];
      return needs.every((part) => task.includes(part)) && !task.includes("TODO");
    },
    tryNext:
      "fill in my_task.py: json_dataset, system_message with judge.txt, generate() and a @scorer",
  },
  {
    says: "my_scores.jsonl has one pass or fail verdict and a reason for every trace",
    test: (folder) => {
      const found = scores(folder);
      const ids = traces(folder).map((row) => text(row.id));
      const scored = found.map((row) => text(row.id));
      const valid = found.every(
        (row) => ["pass", "fail"].includes(text(row.verdict)) && text(row.reason),
      );
      return found.length > 0 && valid && sameIds(ids, scored);
    },
    tryNext: "write one line per trace id: id, verdict (pass or fail) and a one sentence reason",
  },
  {
    says: "the verdicts include both a pass and a fail",
    test: (folder) => {
      const verdicts = new Set(scores(folder).map((row) => text(row.verdict)));
      return verdicts.has("pass") && verdicts.has("fail");
    },
    tryNext:
      "a judge that passes everything tells you nothing; read the fails and check the prompt",
  },
] satisfies Rule[];
