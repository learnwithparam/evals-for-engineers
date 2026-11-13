import { cpSync, existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  idsIn,
  near,
  pairsFor,
  runJudge,
  runScript,
  tprTnr,
  verdictsById,
} from "../parts/03-judge-what-code-cannot/judge-check";
import type { Rule } from "../scripts/verify";
import { once } from "./lib/run";
import { readJson } from "./lib/world";

// The learner writes judge_test.json, so every field may be missing or the wrong type.
type TestReport = {
  prompt_sha256?: unknown;
  tpr?: unknown;
  tnr?: unknown;
  verdicts?: Record<string, unknown>;
};

const report = (folder: string) => readJson<TestReport>(join(folder, "judge_test.json"));

function promptHash(folder: string): string {
  const hasher = new Bun.CryptoHasher("sha256");
  hasher.update(readFileSync(join(folder, "grounded.md")));
  return hasher.digest("hex");
}

/** The verdicts judge_test.json holds, when they cover all 50 test ids with pass or fail. */
function savedVerdicts(folder: string): Map<string, string> | undefined {
  const saved = report(folder).verdicts ?? {};
  const testIds = idsIn("test");
  const byId = new Map(Object.entries(saved).map(([id, verdict]) => [id, String(verdict)]));
  const covered = byId.size === testIds.length && testIds.every((id) => byId.has(id));
  const onlyPassOrFail = [...byId.values()].every((verdict) => /^(pass|fail)$/.test(verdict));
  return covered && onlyPassOrFail ? byId : undefined;
}

const rerun = once((folder: string) => verdictsById(runJudge(folder, "test"), idsIn("test")));

function sameVerdicts(saved: Map<string, string>, again: Map<string, string>): boolean {
  return [...saved.keys()].every((id) => saved.get(id) === again.get(id));
}

const scores = (folder: string) => {
  const saved = savedVerdicts(folder);
  return saved ? tprTnr(pairsFor(saved)) : undefined;
};

// Run test_once.py again in a copy of the folder: it must refuse and leave the result alone.
function secondRunRefused(folder: string): boolean {
  const copy = mkdtempSync(join(tmpdir(), "test-the-judge-"));
  cpSync(folder, copy, { recursive: true });
  const before = readFileSync(join(copy, "judge_test.json"), "utf8");
  const finished = runScript(copy, "test_once.py");
  const after = readFileSync(join(copy, "judge_test.json"), "utf8");
  return finished.code !== 0 && before === after;
}

export default [
  {
    says: "judge_test.json exists, written by test_once.py",
    test: (folder) => existsSync(join(folder, "judge_test.json")),
    tryNext: "run uv run python test_once.py once, after align-the-judge passes",
  },
  {
    says: "judge_test.json was made with the prompt in grounded.md now",
    test: (folder) => report(folder).prompt_sha256 === promptHash(folder),
    tryNext:
      "the prompt changed after the test run; that test number is spent, " +
      "so tune on dev and test a new prompt once",
  },
  {
    says: "it holds a pass or fail verdict for all 50 test answers, and replay gives the same",
    test: (folder) => {
      const saved = savedVerdicts(folder);
      const again = rerun(folder);
      return !!saved && !!again && sameVerdicts(saved, again);
    },
    tryNext: "write the verdicts from run.py into judge_test.json with test_once.py",
  },
  {
    says: "the TPR and TNR in judge_test.json match its verdicts",
    test: (folder) => {
      const recomputed = scores(folder);
      const written = report(folder);
      return !!recomputed && near(written.tpr, recomputed.tpr) && near(written.tnr, recomputed.tnr);
    },
    tryNext: "compute TPR and TNR from the verdicts and Dana's labels in code; never type them",
  },
  {
    says: "TPR and TNR on the test split are both at least 0.80",
    test: (folder) => {
      const recomputed = scores(folder);
      return !!recomputed && recomputed.tpr >= 0.8 && recomputed.tnr >= 0.8;
    },
    tryNext: "go back to align-the-judge, improve the prompt on dev, then test the new prompt once",
  },
  {
    says: "a second test run on the same prompt is refused",
    test: secondRunRefused,
    tryNext:
      "finish already_tested() so test_once.py exits with an error " +
      "when judge_test.json holds this prompt's hash",
  },
] satisfies Rule[];
