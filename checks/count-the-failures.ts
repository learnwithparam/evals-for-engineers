import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { readCsv, readJson, readYaml } from "./lib/world";

const DECISIONS = ["fix the prompt", "code check", "judge", "monitor"];
const rates = (d: string) => readJson(join(d, "rates.json"));
const names = (d: string): string[] => (readYaml(join(d, "failure_modes.yaml"))?.modes ?? []).map((m: any) => m.name);
const labels = (d: string) => readCsv(join(d, "labels.csv"));
const counted = (d: string, m: string) => labels(d).filter((r) => r[m] === "1").length;

export default [
  {
    says: "rates.json has n, top_mode and modes",
    test: (d) => existsSync(join(d, "rates.json")) && typeof rates(d).n === "number" && typeof rates(d).top_mode === "string" && typeof rates(d).modes === "object",
    tryNext: "keep the shape of the starter rates.json and fill it in, or write it from count.py",
  },
  {
    says: "n is the number of reviewed traces in labels.csv",
    test: (d) => rates(d).n === labels(d).length,
    tryNext: "count the rows of labels.csv, not the failed ones",
  },
  {
    says: "every mode has a count and a rate that match labels.csv",
    test: (d) => names(d).every((m) => {
      const e = rates(d).modes?.[m];
      return e && e.count === counted(d, m) && Math.abs(e.rate - counted(d, m) / labels(d).length) < 0.001;
    }),
    tryNext: "compute the numbers from labels.csv with code: count = the 1s in the column, rate = count / n",
  },
  {
    says: "top_mode has the highest count",
    test: (d) => {
      const best = Math.max(...names(d).map((m) => counted(d, m)));
      return names(d).includes(rates(d).top_mode) && counted(d, rates(d).top_mode) === best;
    },
    tryNext: "set top_mode to the mode with the most 1s; if two tie, either is right",
  },
  {
    says: "every mode has a decision: fix the prompt, code check, judge or monitor",
    test: (d) => names(d).every((m) => DECISIONS.includes(rates(d).modes?.[m]?.decision)),
    tryNext: "pick one of the four decisions for each mode, spelled as shown",
  },
  {
    says: "rent failures, which have one right answer, go to a code check",
    test: (d) => names(d).filter((m) => /rent/.test(m)).every((m) => rates(d).modes?.[m]?.decision === "code check"),
    tryNext: "a rent value has one right answer in the lease; compare it in code, do not pay a judge to read it",
  },
] satisfies Rule[];
