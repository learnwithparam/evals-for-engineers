import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { type JsonRecord, readYaml } from "./lib/world";

// The workflow as the learner wrote it. Every key may be missing or the wrong type.
type Step = { run?: unknown; env?: unknown };
type Job = { steps?: unknown; env?: unknown; "timeout-minutes"?: unknown };
type Workflow = { on?: unknown; true?: unknown; jobs?: unknown; env?: unknown };

const GATE_COMMAND = /uv run python gate\.py --release \S+/;
// A model is named by its family. The workflow names none: config/models.py does that.
const MODEL_FAMILY = /\b(claude|gpt|gemini|haiku|sonnet|opus|llama|mistral|qwen)\b/i;
const FROM_SECRETS = /^\$\{\{\s*secrets\.[A-Z0-9_]+\s*\}\}$/;

const workflowPath = (folder: string) => join(folder, "evals.yml");
const workflow = (folder: string) => readYaml<Workflow>(workflowPath(folder)) ?? {};

function jobs(folder: string): Job[] {
  const found = workflow(folder).jobs;
  if (typeof found !== "object" || found === null) return [];
  return Object.values(found as Record<string, Job>);
}

function steps(job: Job): Step[] {
  return Array.isArray(job.steps) ? (job.steps as Step[]) : [];
}

const allSteps = (folder: string) => jobs(folder).flatMap(steps);

// Some YAML readers turn the key "on" into true, so look under both.
function triggers(folder: string): string[] {
  const parsed = workflow(folder);
  const trigger = parsed.on ?? parsed.true;
  if (typeof trigger === "string") return [trigger];
  if (Array.isArray(trigger)) return trigger.map(String);
  if (typeof trigger === "object" && trigger !== null) return Object.keys(trigger);
  return [];
}

function envBlocks(folder: string): JsonRecord[] {
  const blocks = [workflow(folder).env];
  for (const job of jobs(folder)) {
    blocks.push(job.env);
    for (const step of steps(job)) blocks.push(step.env);
  }
  return blocks.filter((block): block is JsonRecord => typeof block === "object" && !!block);
}

function keysComeFromSecrets(folder: string): boolean {
  for (const block of envBlocks(folder)) {
    for (const [name, value] of Object.entries(block)) {
      if (/KEY|TOKEN|SECRET/.test(name) && !FROM_SECRETS.test(String(value).trim())) return false;
    }
  }
  return true;
}

function hasTimeout(job: Job): boolean {
  const minutes = job["timeout-minutes"];
  return typeof minutes === "number" && minutes > 0 && minutes <= 60;
}

export default [
  {
    says: "evals.yml is a workflow with at least one job",
    test: (folder) => existsSync(workflowPath(folder)) && jobs(folder).length > 0,
    tryNext: "keep evals.yml in this problem folder, with a jobs: section that has steps",
  },
  {
    says: "it runs on pull requests",
    test: (folder) => triggers(folder).includes("pull_request"),
    tryNext: "add pull_request under on:, so the gate runs before a merge, not after",
  },
  {
    says: "a step calls the gate: uv run python gate.py --release <name>",
    test: (folder) => allSteps(folder).some((step) => GATE_COMMAND.test(String(step.run ?? ""))),
    tryNext:
      "add a step with run: uv run python gate.py --release <the release>; " +
      "its exit 1 turns the check red",
  },
  {
    says: "every job has a time limit of 60 minutes or less",
    test: (folder) => jobs(folder).length > 0 && jobs(folder).every(hasTimeout),
    tryNext: "add timeout-minutes: 15 to the job, so a hung gate fails instead of waiting",
  },
  {
    says: "LLM_PROVIDER is set for the gate",
    test: (folder) => envBlocks(folder).some((block) => "LLM_PROVIDER" in block),
    tryNext: "set LLM_PROVIDER under env:, for example to replay or to a repo variable",
  },
  {
    says: "every key comes from the repo's secrets, never from the file",
    test: keysComeFromSecrets,
    tryNext:
      "read the key from secrets.ANTHROPIC_API_KEY in a secrets expression, and store the " +
      "value in the repo settings; a key in a file is a leaked key",
  },
  {
    says: "the workflow names no model; config/models.py does that",
    test: (folder) => !MODEL_FAMILY.test(readFileSync(workflowPath(folder), "utf8")),
    tryNext:
      "remove the model name; the gate asks config/models.py for the judge role, " +
      "so the model is set in one place",
  },
] satisfies Rule[];
