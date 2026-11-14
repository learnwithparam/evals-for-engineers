// bun capstone/check.ts <your-folder>: checks your own eval folder, never the course files.
// It proves the shape and that the evidence exists. It cannot tell if your numbers are wise.
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

type Fields = { [field: string]: unknown };
type Rule = { says: string; tryNext: string; test: (folder: string) => boolean };
type Label = { human?: unknown; judge?: unknown };

const MINIMUM_SET = 20;
const COURSE_WORLD = /fernhill|dana mensah|\bL\d{3}(-c\d+)?\b|\bdesk-\d{4}\b/i;

function readJson(path: string): Fields {
  try {
    return existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : {};
  } catch {
    return {};
  }
}

const mine = (folder: string) => readJson(join(folder, "my-eval.json"));
const section = (own: Fields, name: string) => (own[name] ?? {}) as Fields;
const modesOf = (own: Fields) =>
  (Array.isArray(own.failure_modes) ? own.failure_modes : []) as Fields[];
const words = (value: unknown) => (typeof value === "string" ? value.trim() : "");
const isTodo = (value: unknown) => words(value) === "" || words(value).includes("TODO");
const isCount = (value: unknown) => typeof value === "number" && Number.isInteger(value);

function lines(folder: string, relative: unknown): string[] {
  if (typeof relative !== "string" || relative.startsWith("/") || relative.includes(".."))
    return [];
  const path = join(folder, relative);
  if (!existsSync(path)) return [];
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => line.trim());
}

function jsonLines<Shape>(folder: string, relative: unknown): Shape[] {
  try {
    return lines(folder, relative).map((line) => JSON.parse(line) as Shape);
  } catch {
    return [];
  }
}

function traceIds(folder: string): Set<string> {
  const rows = jsonLines<{ id?: unknown }>(folder, mine(folder).traces_path);
  return new Set(rows.map((row) => String(row.id)));
}

// TPR: the judge passes what a person passed. TNR: it fails what a person failed.
function judgeRates(folder: string): { tpr: number; tnr: number; size: number } | null {
  const judge = section(mine(folder), "judge");
  const labels = jsonLines<Label>(folder, judge.labels_path);
  const humanPass = labels.filter((label) => label.human === "pass");
  const humanFail = labels.filter((label) => label.human === "fail");
  if (humanPass.length === 0 || humanFail.length === 0) return null;
  const kept = humanPass.filter((label) => label.judge === "pass").length;
  const caught = humanFail.filter((label) => label.judge === "fail").length;
  return { tpr: kept / humanPass.length, tnr: caught / humanFail.length, size: labels.length };
}

const close = (typed: unknown, computed: number) =>
  typeof typed === "number" && Math.abs(typed - computed) < 0.01;

function everyFileText(folder: string): string {
  const own = mine(folder);
  const names = [
    "my-eval.json",
    own.traces_path,
    section(own, "golden_set").path,
    section(own, "judge").prompt_path,
    section(own, "judge").labels_path,
  ];
  const found = names.filter(
    (name): name is string => typeof name === "string" && !name.includes(".."),
  );
  return found
    .map((name) => (existsSync(join(folder, name)) ? readFileSync(join(folder, name), "utf8") : ""))
    .join("\n");
}

const rules: Rule[] = [
  {
    says: "my-eval.json names your system and has no TODO left",
    test: (folder) => {
      const own = mine(folder);
      return (
        !isTodo(own.system) && modesOf(own).length > 0 && !JSON.stringify(own).includes("TODO")
      );
    },
    tryNext: "fill every field of my-eval.json and remove each TODO",
  },
  {
    says: "your traces file holds a good set of your own traces, and trace_count says how many",
    test: (folder) => {
      const own = mine(folder);
      const found = lines(folder, own.traces_path).length;
      return found >= MINIMUM_SET && own.trace_count === found;
    },
    tryNext:
      "save a good set of your own traces in traces.jsonl and set trace_count to the line count",
  },
  {
    says: "a few failure modes, each with a definition, a count and a real example trace",
    test: (folder) => {
      const modes = modesOf(mine(folder));
      const ids = traceIds(folder);
      const complete = (mode: Fields) =>
        !isTodo(mode.name) &&
        words(mode.definition).split(/\s+/).length >= 5 &&
        isCount(mode.count) &&
        (mode.count as number) >= 1 &&
        ids.has(String(mode.example_trace_id));
      return modes.length >= 3 && modes.length <= 8 && modes.every(complete);
    },
    tryNext:
      "name a few failures, define each in a sentence, and point to a trace id that shows it",
  },
  {
    says: "the failure counts fit inside the trace count",
    test: (folder) => {
      const own = mine(folder);
      const total = modesOf(own).reduce((sum, mode) => sum + Number(mode.count), 0);
      return typeof own.trace_count === "number" && total >= 1 && total <= own.trace_count;
    },
    tryNext: "the counts add up to the failing traces, so the sum cannot pass the trace count",
  },
  {
    says: "the golden set file holds as many cases as golden_set.size says",
    test: (folder) => {
      const golden = section(mine(folder), "golden_set");
      const found = lines(folder, golden.path).length;
      return found >= MINIMUM_SET && golden.size === found;
    },
    tryNext: "write your approved cases in golden.jsonl and set size to the line count",
  },
  {
    says: "the judge has a prompt file and a labels file with as many lines as judge.test_size",
    test: (folder) => {
      const judge = section(mine(folder), "judge");
      const prompt = lines(folder, judge.prompt_path).join("\n");
      const labels = lines(folder, judge.labels_path).length;
      return (
        prompt.length > 0 &&
        !prompt.includes("TODO") &&
        labels >= MINIMUM_SET &&
        judge.test_size === labels
      );
    },
    tryNext:
      "save your judge prompt in judge.txt, one labelled answer per line in judge_labels.jsonl",
  },
  {
    says: "TPR and TNR match what the labels file computes",
    test: (folder) => {
      const judge = section(mine(folder), "judge");
      const computed = judgeRates(folder);
      return computed !== null && close(judge.tpr, computed.tpr) && close(judge.tnr, computed.tnr);
    },
    tryNext:
      "each label line has id, human and judge (pass or fail); copy the rates the check computes",
  },
  {
    says: "the gate names a command and what makes it fail",
    test: (folder) => {
      const gate = section(mine(folder), "gate");
      return !isTodo(gate.command) && words(gate.blocks_on).split(/\s+/).length >= 3;
    },
    tryNext: "write the command your CI runs and the result that blocks a change",
  },
  {
    says: "nothing comes from the course",
    test: (folder) => {
      const text = everyFileText(folder);
      return text.length > 0 && !COURSE_WORLD.test(text);
    },
    tryNext: "describe your own system; remove Fernhill, Dana, lease ids and desk trace ids",
  },
];

const folder = process.argv[2];
if (!folder) {
  console.log("Usage: bun capstone/check.ts <your-folder>");
  process.exit(2);
}
let failed = 0;
for (const rule of rules) {
  const holds = (() => {
    try {
      return rule.test(folder);
    } catch {
      return false;
    }
  })();
  if (holds) console.log(`  PASS  ${rule.says}`);
  else {
    failed += 1;
    console.log(`  FAIL  ${rule.says}\n        Try next: ${rule.tryNext}`);
  }
}
console.log(
  failed === 0
    ? `Done. All ${rules.length} rules pass.`
    : `${failed} of ${rules.length} rules fail.`,
);
process.exit(failed === 0 ? 0 : 1);
