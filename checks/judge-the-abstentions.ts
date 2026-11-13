import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { helperOutput } from "../parts/06-evaluate-retrieval-and-agent/helpers/truth";
import type { Rule } from "../scripts/verify";
import { once, python } from "./lib/run";

const AGREEMENT = 0.8;

type Label = { traceId: string; label: string; split: string };
type JudgeInput = { id: string; answer: string; [field: string]: unknown };
type Truth = { labels: Label[]; inputs: JudgeInput[]; faultFive: string[] };
type Verdict = { id?: unknown; verdict?: unknown; critique?: unknown };

const truth = () => helperOutput<Truth>("abstention_truth.py");

// Replay mode, and no .pyc files left in the learner's folder, as checks/lib/run.ts does.
function replayEnvironment(): Record<string, string | undefined> {
  const environment: Record<string, string | undefined> = { ...process.env };
  environment.LLM_PROVIDER = "replay";
  environment.PYTHONDONTWRITEBYTECODE = "1";
  return environment;
}

/** One fresh run of the learner's judge on every labelled trace. Null when it crashes. */
function judgeRun(folder: string): Verdict[] | null {
  const lines = truth().inputs.map((input) => JSON.stringify(input));
  const ran = Bun.spawnSync([...python(), "abstention_judge.py"], {
    cwd: folder,
    stdin: Buffer.from(lines.join("\n")),
    env: replayEnvironment(),
    timeout: 180_000,
  });
  if (ran.exitCode !== 0) return null;
  const output = ran.stdout.toString().split("\n");
  const filled = output.filter((line) => line.trim());
  return filled.map((line) => JSON.parse(line));
}

// Model behaviour is judged over three fresh runs in replay mode.
const threeJudgeRuns = once((folder) => [judgeRun(folder), judgeRun(folder), judgeRun(folder)]);
const firstRun = (folder: string) => threeJudgeRuns(folder)[0];

function verdictsById(folder: string): Map<string, string> {
  const verdicts = firstRun(folder) ?? [];
  return new Map(verdicts.map((verdict) => [String(verdict.id), String(verdict.verdict)]));
}

function meetsTheContract(folder: string): boolean {
  const verdicts = firstRun(folder);
  if (verdicts === null) return false;
  const ids = verdicts.map((verdict) => String(verdict.id));
  const wanted = truth().inputs.map((input) => input.id);
  const eachOnce = ids.length === wanted.length && new Set(ids).size === ids.length;
  const allAnswered = wanted.every((id) => ids.includes(id));
  const onlyPassOrFail = verdicts.every((verdict) =>
    ["pass", "fail"].includes(String(verdict.verdict)),
  );
  return eachOnce && allAnswered && onlyPassOrFail;
}

function sameEveryRun(folder: string): boolean {
  const runs = threeJudgeRuns(folder);
  if (runs.some((run) => run === null)) return false;
  const verdictLists = runs.map((run) =>
    JSON.stringify((run ?? []).map((verdict) => verdict.verdict)),
  );
  return new Set(verdictLists).size === 1;
}

/** Of the test labels with this label, the share the judge agrees with. */
function agreementOnTest(folder: string, label: string): number {
  const verdicts = verdictsById(folder);
  const test = truth().labels.filter((row) => row.split === "test" && row.label === label);
  const agreed = test.filter((row) => verdicts.get(row.traceId) === label).length;
  return agreed / test.length;
}

/** The prompt must not hold a test answer: a judge that has seen the test is not tested. */
function promptHasNoTestAnswer(folder: string): boolean {
  const judgeFile = join(folder, "abstention_judge.py");
  if (!existsSync(judgeFile)) return false;
  const code = readFileSync(judgeFile, "utf8");
  const testIds = new Set(
    truth()
      .labels.filter((row) => row.split === "test")
      .map((row) => row.traceId),
  );
  const testInputs = truth().inputs.filter((input) => testIds.has(input.id));
  const leaked = testInputs.filter((input) => {
    const answer = input.answer.trim();
    return answer !== "The lease does not say." && code.includes(answer);
  });
  return leaked.length === 0 && [...testIds].every((id) => !code.includes(id));
}

export default [
  {
    says: "abstention_judge.py answers every case once, with pass or fail only",
    test: meetsTheContract,
    tryNext:
      "run uv run python align.py and read the last error line; " +
      "No recorded reply means replay does not know your prompt (see If you get stuck)",
  },
  {
    says: "the judge gives the same verdicts over three fresh runs",
    test: sameEveryRun,
    tryNext: "keep temperature and prompt fixed; do not add random examples to the prompt",
  },
  {
    says: "TPR is 0.80 or more on the test split",
    test: (folder) => firstRun(folder) !== null && agreementOnTest(folder, "pass") >= AGREEMENT,
    tryNext:
      "your judge fails good answers; in align.py, read the cases where Dana says pass " +
      'and the judge says fail, such as a right "The lease does not say."',
  },
  {
    says: "TNR is 0.80 or more on the test split",
    test: (folder) => firstRun(folder) !== null && agreementOnTest(folder, "fail") >= AGREEMENT,
    tryNext:
      "your judge passes answers Dana fails; add a rule that fails a claim " +
      "when no clause found answers the question",
  },
  {
    says: "every planted fault 5 answer is caught",
    test: (folder) => {
      const verdicts = verdictsById(folder);
      return (
        firstRun(folder) !== null && truth().faultFive.every((id) => verdicts.get(id) === "fail")
      );
    },
    tryNext:
      "fault 5 is an answer to a question the lease does not answer; your judge must fail it",
  },
  {
    says: "the prompt holds no test trace and no test answer",
    test: promptHasNoTestAnswer,
    tryNext:
      "write rules in CRITERION, not examples copied from the test split; " +
      "use the dev labels in abstention_dev.csv to align",
  },
] satisfies Rule[];
