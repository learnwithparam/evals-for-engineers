import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";

// The learner writes my-eval.json by hand, so every field may be missing or the wrong type.
type Mode = { name?: unknown; definition?: unknown; count?: unknown; example_trace_id?: unknown };
type MyEval = {
  system?: unknown;
  trace_count?: unknown;
  traces_path?: unknown;
  failure_modes?: Mode[];
  golden_set?: { path?: unknown; size?: unknown };
  judge?: { prompt_path?: unknown; test_size?: unknown; tpr?: unknown; tnr?: unknown };
  gate?: { command?: unknown; blocks_on?: unknown };
};

const MINIMUM_SET = 20;
const COURSE_WORLD = /fernhill|dana mensah|\bL\d{3}(-c\d+)?\b|\bdesk-\d{4}\b/i;

function mine(folder: string): MyEval {
  const path = join(folder, "my-eval.json");
  return existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : {};
}

const words = (value: unknown) => (typeof value === "string" ? value.trim() : "");
const isTodo = (value: unknown) => words(value) === "" || words(value).includes("TODO");
const isCount = (value: unknown) => typeof value === "number" && Number.isInteger(value);
const isRate = (value: unknown) => typeof value === "number" && value >= 0 && value <= 1;

function lines(folder: string, relative: unknown): string[] {
  if (typeof relative !== "string" || relative.startsWith("/") || relative.includes("..")) return [];
  const path = join(folder, relative);
  if (!existsSync(path)) return [];
  return readFileSync(path, "utf8").split("\n").filter((line) => line.trim());
}

function traceIds(folder: string): Set<string> {
  const ids = lines(folder, mine(folder).traces_path).map((line) => JSON.parse(line).id);
  return new Set(ids.map(String));
}

function everyFileText(folder: string): string {
  const own = mine(folder);
  const names = ["my-eval.json", own.traces_path, own.golden_set?.path, own.judge?.prompt_path];
  const found = names.filter((name): name is string => typeof name === "string");
  return found.map((name) => readFileSync(join(folder, name), "utf8")).join("\n");
}

export default [
  {
    says: "my-eval.json names your system and has no TODO left",
    test: (folder) => {
      const own = mine(folder);
      const modes = own.failure_modes ?? [];
      const leftover = JSON.stringify(own).includes("TODO");
      return !isTodo(own.system) && modes.length > 0 && !leftover;
    },
    tryNext: "fill every field of my-eval.json; remove each TODO",
  },
  {
    says: "traces_path points to at least 20 traces, and trace_count says how many",
    test: (folder) => {
      const own = mine(folder);
      const found = lines(folder, own.traces_path).length;
      return found >= MINIMUM_SET && own.trace_count === found;
    },
    tryNext: "save 20 or more of your own traces in traces.jsonl and set trace_count to that number",
  },
  {
    says: "3 to 8 failure modes, each with a definition, a count and a real example trace",
    test: (folder) => {
      const modes = mine(folder).failure_modes ?? [];
      const ids = traceIds(folder);
      const complete = (mode: Mode) =>
        !isTodo(mode.name) &&
        words(mode.definition).split(/\s+/).length >= 5 &&
        isCount(mode.count) &&
        (mode.count as number) >= 1 &&
        ids.has(String(mode.example_trace_id));
      return modes.length >= 3 && modes.length <= 8 && modes.every(complete);
    },
    tryNext: "name 3 to 8 failures, define each in a sentence, and point to a trace id that shows it",
  },
  {
    says: "the failure counts fit inside the trace count",
    test: (folder) => {
      const own = mine(folder);
      const total = (own.failure_modes ?? []).reduce((sum, mode) => sum + Number(mode.count), 0);
      return typeof own.trace_count === "number" && total >= 1 && total <= own.trace_count;
    },
    tryNext: "the counts add up to the failing traces, so the sum cannot pass the trace count",
  },
  {
    says: "golden_set.path holds as many cases as golden_set.size, at least 20",
    test: (folder) => {
      const golden = mine(folder).golden_set;
      const found = lines(folder, golden?.path).length;
      return found >= MINIMUM_SET && golden?.size === found;
    },
    tryNext: "write 20 or more approved cases in golden.jsonl and set size to the line count",
  },
  {
    says: "the judge has a prompt file, a test size of at least 20, and TPR and TNR between 0 and 1",
    test: (folder) => {
      const judge = mine(folder).judge;
      const prompt = lines(folder, judge?.prompt_path).join("\n");
      const sized = typeof judge?.test_size === "number" && judge.test_size >= MINIMUM_SET;
      return prompt.length > 0 && sized && isRate(judge?.tpr) && isRate(judge?.tnr);
    },
    tryNext: "save your judge prompt in judge.txt and report TPR and TNR from 20 or more test labels",
  },
  {
    says: "the gate names a command and what makes it fail",
    test: (folder) => {
      const gate = mine(folder).gate;
      return !isTodo(gate?.command) && words(gate?.blocks_on).split(/\s+/).length >= 3;
    },
    tryNext: "write the command your CI runs and the result that blocks a change",
  },
  {
    says: "nothing comes from the course world",
    test: (folder) => {
      const text = everyFileText(folder);
      return text.length > 0 && !COURSE_WORLD.test(text);
    },
    tryNext: "describe your own system; remove Fernhill, Dana, lease ids and desk trace ids",
  },
] satisfies Rule[];
