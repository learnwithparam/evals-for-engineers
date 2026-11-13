import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { productionTruth } from "../parts/05-watch-production/helpers/production";
import type { Rule } from "../scripts/verify";
import { DATA, readJsonl } from "./lib/world";

const ABSTAIN = "The lease does not say.";
const FIELDS = [
  "id",
  "source",
  "trace_id",
  "lease_id",
  "question",
  "gold_clauses",
  "must_say",
  "critique",
];
// The review cases the starter golden set holds. Feeding failures back adds cases, never removes.
const STARTER_IDS = [
  "review-q011",
  "review-q054",
  "review-q029",
  "review-q021",
  "review-q036",
  "review-q048",
  "review-q069",
];

// One golden case as the learner wrote it, so any field may be missing or the wrong type.
type GoldenCase = Record<string, unknown>;
type DeskTrace = { [field: string]: unknown; cited: string[]; answer: string };

const goldenFile = (folder: string) => join(folder, "golden_desk.jsonl");
const cases = (folder: string) => readJsonl<GoldenCase>(goldenFile(folder));
const productionCases = (folder: string) =>
  cases(folder).filter((golden) => golden.source === "production");

let cachedTraces: Map<string, DeskTrace> | undefined;
function productionTraces(): Map<string, DeskTrace> {
  if (cachedTraces === undefined) {
    const traces = readJsonl<DeskTrace>(join(DATA, "traces", "lease_desk_production.jsonl"));
    cachedTraces = new Map(traces.map((trace) => [String(trace.trace_id), trace]));
  }
  return cachedTraces;
}

/** Dana's truth: was the production answer grounded in the lease? */
function groundedTruth(): Map<string, boolean> {
  const rows = readJsonl(join(DATA, "labels", "production_truth.jsonl"));
  return new Map(rows.map((row) => [String(row.trace_id), row.grounded === true]));
}

/** The clauses that answer a question, as the world wrote them when it made the question. */
function rightClauses(questionId: string, leaseId: string): string[] {
  if (questionId.endsWith("-renewal")) return [`${leaseId}-c12`];
  if (questionId.endsWith("-rent")) return [`${leaseId}-c04`];
  const questions = readJsonl(join(DATA, "questions.jsonl"));
  const question = questions.find((candidate) => candidate.id === questionId);
  return (question?.gold as string[] | undefined) ?? [];
}

/** The text of one clause, read from the lease file: "## c04 Rent" starts clause L126-c04. */
function clauseText(clauseId: string): string {
  const [leaseId, clauseNumber] = clauseId.split("-");
  const leaseFile = join(DATA, "leases", `${leaseId}.md`);
  if (!existsSync(leaseFile)) return "";
  const sections = readFileSync(leaseFile, "utf8").split(/^## /m);
  const section = sections.find((text) => text.startsWith(`${clauseNumber} `));
  if (section === undefined) return "";
  return section.split("\n").slice(1).join(" ");
}

function matchesItsTrace(golden: GoldenCase): boolean {
  const trace = productionTraces().get(String(golden.trace_id));
  if (trace === undefined) return false;
  return trace.lease_id === golden.lease_id && trace.question === golden.question;
}

function hasTheRightClauses(golden: GoldenCase): boolean {
  const trace = productionTraces().get(String(golden.trace_id));
  if (trace === undefined || !Array.isArray(golden.gold_clauses)) return false;
  const wanted = rightClauses(String(trace.question_id), String(trace.lease_id));
  const given = [...golden.gold_clauses].sort();
  return JSON.stringify(given) === JSON.stringify(wanted.sort());
}

function mustSayComesFromTheLease(golden: GoldenCase): boolean {
  const gold = golden.gold_clauses as string[];
  const mustSay = String(golden.must_say ?? "").trim();
  if (gold.length === 0) return mustSay === ABSTAIN;
  if (mustSay.length < 3) return false;
  return gold.some((clauseId) =>
    clauseText(clauseId).toLowerCase().includes(mustSay.toLowerCase()),
  );
}

/** The same rule as score_live.py: live passes when it cites every gold clause and says it. */
function livePasses(golden: GoldenCase): boolean {
  const trace = productionTraces().get(String(golden.trace_id));
  if (trace === undefined) return false;
  const gold = golden.gold_clauses as string[];
  if (gold.length === 0) return trace.answer.trim() === ABSTAIN;
  const citesEveryGold = gold.every((clauseId) => trace.cited.includes(clauseId));
  const saysIt = trace.answer.toLowerCase().includes(String(golden.must_say).toLowerCase());
  return citesEveryGold && saysIt;
}

function everyProductionCase(folder: string, test: (golden: GoldenCase) => boolean): boolean {
  const added = productionCases(folder);
  return added.length > 0 && added.every(test);
}

const hasEveryField = (golden: GoldenCase) => FIELDS.every((field) => field in golden);

function critiqueHasFiveWords(golden: GoldenCase): boolean {
  const words = String(golden.critique ?? "")
    .trim()
    .split(/\s+/);
  return words.length >= 5;
}

export default [
  {
    says: "golden_desk.jsonl reads, and every case has all eight fields",
    test: (folder) => existsSync(goldenFile(folder)) && cases(folder).every(hasEveryField),
    tryNext:
      "copy a review line as the shape for a new case; " +
      "each line is one JSON object with id, source, trace_id, lease_id, question, " +
      "gold_clauses, must_say and critique",
  },
  {
    says: "every review case from the starter is still there",
    test: (folder) => {
      const ids = new Set(cases(folder).map((golden) => golden.id));
      return STARTER_IDS.every((id) => ids.has(id));
    },
    tryNext: "add new lines at the end of golden_desk.jsonl and keep the review lines",
  },
  {
    says: 'at least 3 cases are tagged "source": "production"',
    test: (folder) => productionCases(folder).length >= 3,
    tryNext: 'set "source": "production" on each case you take from a production trace',
  },
  {
    says: "each production case names a real production trace, with its lease and question",
    test: (folder) => everyProductionCase(folder, matchesItsTrace),
    tryNext:
      "copy trace_id, lease_id and question from the trace's line in " +
      "world/data/traces/lease_desk_production.jsonl",
  },
  {
    says: "gold_clauses are the clauses that answer the question",
    test: (folder) => everyProductionCase(folder, hasTheRightClauses),
    tryNext:
      "open the lease with uv run world lease <id> and find the clause that answers; " +
      "rent is in c04 and an extension in c12, not the clause live cited",
  },
  {
    says: "must_say is words from a gold clause, not from live's answer",
    test: (folder) => everyProductionCase(folder, mustSayComesFromTheLease),
    tryNext:
      "copy must_say from the lease, such as $1,950.00 or at least 60 days; " +
      "a phrase from the wrong answer makes the wrong answer pass",
  },
  {
    says: "live fails every production case, and Dana's truth agrees it was wrong",
    test: (folder) => {
      const truth = groundedTruth();
      const wrongInTruth = (golden: GoldenCase) => truth.get(String(golden.trace_id)) === false;
      const realFailure = (golden: GoldenCase) => !livePasses(golden) && wrongInTruth(golden);
      return everyProductionCase(folder, realFailure);
    },
    tryNext:
      "take traces the judge marked fail in verdicts.jsonl, and run uv run python score_live.py; " +
      "a case live already passes teaches the gate nothing",
  },
  {
    says: "at least one production case is on a template the golden set lacks",
    test: (folder) =>
      productionCases(folder).some(
        (golden) => productionTruth().get(String(golden.trace_id))?.unseen === true,
      ),
    tryNext: 'pick a failure where "template" is FH-RES-2026 in verdicts.jsonl',
  },
  {
    says: "every production case has a critique of 5 or more words",
    test: (folder) => everyProductionCase(folder, critiqueHasFiveWords),
    tryNext: "say in one sentence what the answer got wrong, as you did in note-the-failures",
  },
] satisfies Rule[];
