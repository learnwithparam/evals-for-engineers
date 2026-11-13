import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import {
  heldOutTextIn,
  idsIn,
  runJudge,
  type Verdict,
} from "../parts/03-judge-what-code-cannot/judge-check";
import type { Rule } from "../scripts/verify";
import { once } from "./lib/run";

// Behaviour that depends on a model is judged over three fresh runs in replay mode.
const threeJudgeRuns = once((folder: string) => [1, 2, 3].map(() => runJudge(folder, "train")));
const firstRun = (folder: string) => threeJudgeRuns(folder)[0];
const prompt = (folder: string) => readFileSync(join(folder, "grounded.txt"), "utf8");

function everyIdOnce(verdicts: Verdict[] | undefined): boolean {
  if (!verdicts) return false;
  const answered = verdicts.map((verdict) => String(verdict.id));
  const trainIds = idsIn("train");
  const noRepeats = new Set(answered).size === answered.length;
  return (
    noRepeats &&
    answered.length === trainIds.length &&
    trainIds.every((id) => answered.includes(id))
  );
}

const onlyPassOrFail = (verdicts: Verdict[] | undefined) =>
  !!verdicts?.length &&
  verdicts.every((verdict) => verdict.verdict === "pass" || verdict.verdict === "fail");

const verdictText = (verdicts: Verdict[] | undefined) =>
  JSON.stringify((verdicts ?? []).map((verdict) => [verdict.id, verdict.verdict]));

export default [
  {
    says: "grounded.txt holds a judge prompt",
    test: (folder) => existsSync(join(folder, "grounded.txt")) && !/TODO/.test(prompt(folder)),
    tryNext: "replace the TODO lines in grounded.txt with your prompt: one criterion, pass or fail",
  },
  {
    says: "the prompt asks for a critique before the verdict",
    test: (folder) => {
      const text = prompt(folder).toLowerCase();
      const critique = text.indexOf("critique");
      return critique >= 0 && critique < text.lastIndexOf("verdict");
    },
    tryNext: 'ask for JSON with "critique" first and "verdict" after, so the judge reasons first',
  },
  {
    says: "the prompt holds no dev or test answer",
    test: (folder) => heldOutTextIn(prompt(folder)) === undefined,
    tryNext: "take examples only from the 20 train answers; dev and test must stay unseen",
  },
  {
    says: "run.py answers the 20 train cases",
    test: (folder) => firstRun(folder) !== undefined,
    tryNext:
      "run uv run python cases.py train | uv run python run.py and read the error; " +
      "with no key, replay knows only recorded prompts",
  },
  {
    says: "every train id is answered exactly once",
    test: (folder) => everyIdOnce(firstRun(folder)),
    tryNext: "print one JSON line per input line, with the same id, and nothing else on stdout",
  },
  {
    says: 'every verdict is "pass" or "fail", never a score',
    test: (folder) => onlyPassOrFail(firstRun(folder)),
    tryNext: 'write the verdict in lower case, exactly "pass" or "fail"; no scores, no "Pass"',
  },
  {
    says: "three runs give the same verdicts",
    test: (folder) => {
      const [first, second, third] = threeJudgeRuns(folder).map(verdictText);
      return !!firstRun(folder) && first === second && second === third;
    },
    tryNext: "keep the judge at temperature 0 and read each reply from one recording",
  },
] satisfies Rule[];
