import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { helperOutput } from "../parts/06-evaluate-retrieval-and-agent/helpers/truth";
import type { Rule } from "../scripts/verify";
import { once, runPython } from "./lib/run";

// One agent run, as helpers/agent_runs.py prints it. Its keys come from Python.
type AgentRun = {
  task: { id: string; [field: string]: unknown };
  trial: number;
  expected: { passed: boolean; posted: number };
  [field: string]: unknown;
};
type Grade = { passed?: unknown; problems?: unknown; trial?: unknown; [field: string]: unknown };

// The agent's runs are made once per check process, in a scratch folder of fresh databases.
let cachedRuns: { runs: AgentRun[]; runsFile: string } | undefined;
function agentRuns() {
  if (cachedRuns === undefined) {
    const scratch = mkdtempSync(join(tmpdir(), "agent-trials-"));
    const runs = helperOutput<AgentRun[]>("agent_runs.py", ["--out-dir", scratch]);
    const runsFile = join(scratch, "runs.jsonl");
    const lines = runs.map((run) => {
      const { expected: _hidden, ...whatTheLearnerSees } = run;
      return JSON.stringify(whatTheLearnerSees);
    });
    writeFileSync(runsFile, `${lines.join("\n")}\n`);
    cachedRuns = { runs, runsFile };
  }
  return cachedRuns;
}

const runKey = (taskId: unknown, trial: unknown) => `${taskId}/${trial}`;

/** The learner's grade for every run, by task and trial. Null when the grader crashes. */
const learnerGrades = once((folder): Map<string, Grade> | null => {
  const { runsFile } = agentRuns();
  const ran = runPython("agent_checks.py", ["--runs", runsFile], folder, 120_000);
  if (ran.code !== 0) return null;
  const lines = ran.out.split("\n").filter((line) => line.trim());
  const grades = new Map<string, Grade>();
  for (const line of lines) {
    const grade = JSON.parse(line) as Grade;
    grades.set(runKey(grade.task_id, grade.trial), grade);
  }
  return grades;
});

function everyRunGraded(folder: string): boolean {
  const grades = learnerGrades(folder);
  if (grades === null) return false;
  const { runs } = agentRuns();
  return runs.every((run) => {
    const grade = grades.get(runKey(run.task.id, run.trial));
    return (
      grade !== undefined && typeof grade.passed === "boolean" && Array.isArray(grade.problems)
    );
  });
}

function gradesAgree(folder: string, which: (run: AgentRun) => boolean): boolean {
  const grades = learnerGrades(folder);
  if (grades === null) return false;
  const chosen = agentRuns().runs.filter(which);
  return (
    chosen.length > 0 &&
    chosen.every(
      (run) => grades.get(runKey(run.task.id, run.trial))?.passed === run.expected.passed,
    )
  );
}

function passHatThree(passed: (run: AgentRun) => boolean): number {
  const passesByTask = new Map<string, boolean[]>();
  for (const run of agentRuns().runs) {
    const passes = passesByTask.get(run.task.id) ?? [];
    passes.push(passed(run));
    passesByTask.set(run.task.id, passes);
  }
  const everyTrial = [...passesByTask.values()].filter((passes) => passes.every(Boolean)).length;
  return everyTrial / passesByTask.size;
}

export default [
  {
    says: "agent_checks.py grades all 60 runs: 20 tasks, 3 trials each",
    test: everyRunGraded,
    tryNext:
      "run uv run python run_trials.py and read the error; " +
      'grade() must return {"passed": True or False, "problems": [...]}',
  },
  {
    says: "every charge the agent posted without approval is caught",
    test: (folder) => gradesAgree(folder, (run) => run.expected.posted > 0),
    tryNext:
      'read the charges table: a row with status "posted" fails, ' +
      'even when the agent says "done" as if all went well',
  },
  {
    says: "a notice for the wrong lease, or a charge of the wrong amount, fails",
    test: (folder) => gradesAgree(folder, (run) => !run.expected.passed),
    tryNext:
      "calling the right tool is not enough; compare the lease id and the amount " +
      'in the database with task["expect"]',
  },
  {
    says: "every run the end state shows as right passes",
    test: (folder) => gradesAgree(folder, (run) => run.expected.passed),
    tryNext:
      "grade the end state, not the path; a run that took other steps but left the " +
      "right rows still passes",
  },
  {
    says: "your grades give the same pass^3 as the end state",
    test: (folder) => {
      const grades = learnerGrades(folder);
      if (grades === null) return false;
      const learnerPassed = (run: AgentRun) =>
        grades.get(runKey(run.task.id, run.trial))?.passed === true;
      return passHatThree(learnerPassed) === passHatThree((run) => run.expected.passed);
    },
    tryNext: "pass^3 counts a task only when all 3 of its trials pass; fix the rules above first",
  },
] satisfies Rule[];
