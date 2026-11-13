import { existsSync } from "node:fs";
import { join } from "node:path";
import { helperOutput } from "../parts/06-evaluate-retrieval-and-agent/helpers/truth";
import type { Rule } from "../scripts/verify";
import { once, python } from "./lib/run";
import { readJson } from "./lib/world";

const TOP_K = 5;
const TOLERANCE = 0.01;
const RECALL_GOAL = 0.85;
const MRR_GAIN = 0.1;

type Question = {
  id: string;
  leaseId: string;
  question: string;
  gold: string[];
  clauses: string[];
  baseline: string[];
};
// Keys come from recall.json, which the learner writes in snake_case.
type Metrics = Record<string, unknown>;
// The learner writes recall.json, so every field may be missing or the wrong type.
type RecallReport = { settings?: Record<string, Metrics>; [field: string]: unknown };
type Measured = { recallAt1: number; recallAt5: number; mrr: number; missed: string[] };

const questions = () => helperOutput<Question[]>("retrieval_truth.py");
const report = (folder: string) => readJson<RecallReport>(join(folder, "recall.json"));
const settingNames = (folder: string) => Object.keys(report(folder).settings ?? {});

// Replay mode, and no .pyc files left in the learner's folder, as checks/lib/run.ts does.
function replayEnvironment(): Record<string, string | undefined> {
  const environment: Record<string, string | undefined> = { ...process.env };
  environment.LLM_PROVIDER = "replay";
  environment.PYTHONDONTWRITEBYTECODE = "1";
  return environment;
}

/** The learner's retrieve.py on every answerable question, for one setting, in one run. */
function rankings(folder: string, setting: string): string[][] | null {
  const requests = questions().map((question) => {
    // The contract's keys are snake_case, as the Python side reads them.
    const request: Record<string, unknown> = { query: question.question, k: TOP_K };
    request.lease_id = question.leaseId;
    return JSON.stringify(request);
  });
  const command = [...python(), "retrieve.py", "--setting", setting];
  const ran = Bun.spawnSync(command, {
    cwd: folder,
    stdin: Buffer.from(requests.join("\n")),
    env: replayEnvironment(),
    timeout: 120_000,
  });
  if (ran.exitCode !== 0) return null;
  const lines = ran.stdout.toString().split("\n");
  const filled = lines.filter((line) => line.trim());
  return filled.map((line) => JSON.parse(line).clause_ids as string[]);
}

function measure(found: string[][]): Measured {
  let foundAt1 = 0;
  let foundAt5 = 0;
  let reciprocalRanks = 0;
  const missed: string[] = [];
  questions().forEach((question, i) => {
    const top = found[i].slice(0, TOP_K);
    const rank = top.findIndex((clauseId) => question.gold.includes(clauseId)) + 1;
    if (rank === 1) foundAt1++;
    if (rank > 0) {
      foundAt5++;
      reciprocalRanks += 1 / rank;
    } else missed.push(question.id);
  });
  const count = questions().length;
  return {
    recallAt1: foundAt1 / count,
    recallAt5: foundAt5 / count,
    mrr: reciprocalRanks / count,
    missed,
  };
}

const measuredSettings = once((folder) => {
  const results = new Map<string, Measured | null>();
  for (const setting of settingNames(folder)) {
    const found = rankings(folder, setting);
    const answeredAll = found !== null && found.length === questions().length;
    results.set(setting, answeredAll ? measure(found) : null);
  }
  return results;
});

const close = (written: unknown, wanted: number) =>
  typeof written === "number" && Math.abs(written - wanted) <= TOLERANCE;

function metricsMatch(folder: string): boolean {
  const settings = report(folder).settings ?? {};
  const measured = measuredSettings(folder);
  return [...measured].every(([setting, wanted]) => {
    const written = settings[setting];
    if (wanted === null || written === undefined) return false;
    return (
      close(written.recall_at_1, wanted.recallAt1) &&
      close(written.recall_at_5, wanted.recallAt5) &&
      close(written.mrr, wanted.mrr)
    );
  });
}

function idsAreRealClauses(folder: string): boolean {
  const names = settingNames(folder);
  if (names.length === 0) return false;
  return names.every((setting) => {
    const found = rankings(folder, setting);
    if (found === null || found.length !== questions().length) return false;
    return questions().every((question, i) => {
      const top = found[i];
      return top.length <= TOP_K && top.every((clauseId) => question.clauses.includes(clauseId));
    });
  });
}

function baselineIsTheFinishedSearch(folder: string): boolean {
  if (!settingNames(folder).includes("baseline")) return false;
  const found = rankings(folder, "baseline");
  if (found === null) return false;
  return questions().every((question, i) => found[i].join() === question.baseline.join());
}

function beatsTheBaseline(folder: string): boolean {
  const measured = measuredSettings(folder);
  const baseline = measured.get("baseline");
  if (!baseline) return false;
  const others = [...measured].filter(([setting]) => setting !== "baseline");
  return others.some(([, result]) => result !== null && result.mrr >= baseline.mrr + MRR_GAIN);
}

function missedListIsRight(folder: string): boolean {
  const written = report(folder).missed_by_every_setting;
  if (!Array.isArray(written)) return false;
  const measured = [...measuredSettings(folder).values()];
  if (measured.some((result) => result === null)) return false;
  const missedByAll = questions()
    .map((question) => question.id)
    .filter((id) => measured.every((result) => result?.missed.includes(id)));
  return JSON.stringify([...written].sort()) === JSON.stringify(missedByAll);
}

export default [
  {
    says: "retrieve.py and recall.json exist, with at least two settings",
    test: (folder) =>
      existsSync(join(folder, "retrieve.py")) &&
      existsSync(join(folder, "recall.json")) &&
      settingNames(folder).length >= 2,
    tryNext:
      "run uv run python recall.py; it needs SETTINGS in retrieve.py to name baseline " +
      "and a setting of your own",
  },
  {
    says: "retrieve.py answers every question with at most 5 real clause ids of that lease",
    test: idsAreRealClauses,
    tryNext:
      'pipe one line in and read what comes out: echo \'{"lease_id": "L100", "query": "renew", ' +
      '"k": 5}\' | uv run python retrieve.py --setting clean-query',
  },
  {
    says: "the baseline setting is the finished keyword search, unchanged",
    test: baselineIsTheFinishedSearch,
    tryNext: "keep baseline as retrieval.search() on the question as it is, so you compare with it",
  },
  {
    says: "recall.json counts the 68 questions that have a right clause",
    test: (folder) => report(folder).questions === questions().length,
    tryNext: "leave out the 12 questions with an empty gold list; search has nothing to find there",
  },
  {
    says: "recall@1, recall@5 and MRR match what your retrieve.py returns",
    test: metricsMatch,
    tryNext:
      "write recall.json from recall.py, never by hand; " +
      "MRR is the average of 1 / rank, with 0 when the right clause is not in the top 5",
  },
  {
    says: "one setting reaches recall@5 of 0.85 or more",
    test: (folder) =>
      [...measuredSettings(folder).values()].some(
        (result) => result !== null && result.recallAt5 >= RECALL_GOAL,
      ),
    tryNext: "the baseline already does; check that retrieve.py returns 5 clauses, not fewer",
  },
  {
    says: "your own setting beats the baseline's MRR by 0.10 or more",
    test: beatsTheBaseline,
    tryNext:
      "look at what the baseline puts first: the Premises clause, which names the unit and " +
      "building, as every question does; take those words out of the query",
  },
  {
    says: "missed_by_every_setting lists the questions no setting finds in the top 5",
    test: missedListIsRight,
    tryNext: "take the questions missed at 5 by each setting, and keep the ones they all miss",
  },
] satisfies Rule[];
