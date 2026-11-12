import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { readCsv, readJson, readYaml } from "./lib/world";

const DECISIONS = ["fix the prompt", "code check", "judge", "monitor"];

// The learner writes rates.json, so every field may be missing or the wrong type.
type ModeRate = { count?: unknown; rate?: unknown; decision?: unknown };
type Rates = {
  n?: unknown;
  modes?: Record<string, ModeRate | undefined>;
  [field: string]: unknown;
};
type FailureModes = { modes?: { name: string }[] };

const rates = (folder: string) => readJson<Rates>(join(folder, "rates.json"));
const topMode = (folder: string) => rates(folder).top_mode as string;
const modeRate = (folder: string, mode: string) => rates(folder).modes?.[mode];

const names = (folder: string): string[] => {
  const failureModes = readYaml<FailureModes | undefined>(join(folder, "failure_modes.yaml"));
  return (failureModes?.modes ?? []).map((mode) => mode.name);
};
const labels = (folder: string) => readCsv(join(folder, "labels.csv"));
const counted = (folder: string, mode: string) =>
  labels(folder).filter((row) => row[mode] === "1").length;

function matchesLabels(folder: string, mode: string): boolean {
  const entry = modeRate(folder, mode);
  if (!entry) return false;
  const count = counted(folder, mode);
  const rate = count / labels(folder).length;
  return entry.count === count && Math.abs(Number(entry.rate) - rate) < 0.001;
}

export default [
  {
    says: "rates.json has n, top_mode and modes",
    test: (folder) =>
      existsSync(join(folder, "rates.json")) &&
      typeof rates(folder).n === "number" &&
      typeof rates(folder).top_mode === "string" &&
      typeof rates(folder).modes === "object",
    tryNext: "keep the shape of the starter rates.json and fill it in, or write it from count.py",
  },
  {
    says: "n is the number of reviewed traces in labels.csv",
    test: (folder) => rates(folder).n === labels(folder).length,
    tryNext: "count the rows of labels.csv, not the failed ones",
  },
  {
    says: "every mode has a count and a rate that match labels.csv",
    test: (folder) => names(folder).every((mode) => matchesLabels(folder, mode)),
    tryNext:
      "compute the numbers from labels.csv with code: " +
      "count = the 1s in the column, rate = count / n",
  },
  {
    says: "top_mode has the highest count",
    test: (folder) => {
      const counts = names(folder).map((mode) => counted(folder, mode));
      const best = Math.max(...counts);
      const top = topMode(folder);
      return names(folder).includes(top) && counted(folder, top) === best;
    },
    tryNext: "set top_mode to the mode with the most 1s; if two tie, either is right",
  },
  {
    says: "every mode has a decision: fix the prompt, code check, judge or monitor",
    test: (folder) =>
      names(folder).every((mode) => {
        const decision = modeRate(folder, mode)?.decision;
        return DECISIONS.includes(decision as string);
      }),
    tryNext: "pick one of the four decisions for each mode, spelled as shown",
  },
  {
    says: "rent failures, which have one right answer, go to a code check",
    test: (folder) => {
      const rentModes = names(folder).filter((mode) => /rent/.test(mode));
      return rentModes.every((mode) => modeRate(folder, mode)?.decision === "code check");
    },
    tryNext:
      "a rent value has one right answer in the lease; " +
      "compare it in code, do not pay a judge to read it",
  },
] satisfies Rule[];
