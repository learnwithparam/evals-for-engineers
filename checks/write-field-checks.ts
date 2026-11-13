import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { once, runPython } from "./lib/run";

// A known pair: what the abstractor wrote (got), the approved value (want), and the right verdict.
type Pair = {
  id: string;
  field: string;
  got: unknown;
  want: unknown;
  right: "pass" | "fail";
  lease?: Record<string, unknown>;
};
type Verdict = { id?: unknown; verdict?: unknown; reason?: unknown };
type Accuracy = { overall?: unknown; fields?: Record<string, unknown> };

const pass = (id: string, field: string, got: unknown, want: unknown): Pair => ({
  id,
  field,
  got,
  want,
  right: "pass",
});
const fail = (id: string, field: string, got: unknown, want: unknown): Pair => ({
  id,
  field,
  got,
  want,
  right: "fail",
});

// Money: the approved value is in cents. Text is in dollars. Floats of dollars break on $0.30.
const MONEY_PAIRS: Pair[] = [
  pass("money-01", "monthly_rent", 282500, 282500),
  pass("money-02", "monthly_rent", "$2,825.00", 282500),
  pass("money-03", "monthly_rent", "2825", 282500),
  pass("money-04", "monthly_rent", "2,825.00", 282500),
  fail("money-05", "monthly_rent", 265000, 282500),
  fail("money-06", "monthly_rent", "$2,650.00", 282500),
  pass("money-07", "deposit", "$3,750.00", 375000),
  fail("money-08", "deposit", 345000, 315000),
  pass("money-09", "pet_fee", "25", 2500),
  fail("money-10", "pet_fee", "$25.01", 2500),
  pass("money-11", "early_termination_fee", null, null),
  fail("money-12", "early_termination_fee", 375000, null),
  pass("money-13", "monthly_rent", "$1,716.00", 171600),
  fail("money-14", "monthly_rent", "1716.1", 171600),
  pass("money-15", "pet_fee", "$0.30", 30),
  pass("money-16", "monthly_rent", "$1,234.56", 123456),
];

// Dates: the approved value is ISO. Leases write dates in words.
const DATE_PAIRS: Pair[] = [
  pass("date-01", "start_date", "2026-03-01", "2026-03-01"),
  pass("date-02", "start_date", "1st day of March, 2026", "2026-03-01"),
  pass("date-03", "start_date", "1 March 2026", "2026-03-01"),
  pass("date-04", "start_date", "March 1, 2026", "2026-03-01"),
  pass("date-05", "start_date", "the 1st day of March 2026", "2026-03-01"),
  fail("date-06", "start_date", "2026-01-03", "2026-03-01"),
  fail("date-07", "start_date", "3 January 2026", "2026-03-01"),
  pass("date-08", "end_date", "31 August 2027", "2027-08-31"),
  fail("date-09", "end_date", "2027-08-30", "2027-08-31"),
  fail("date-10", "end_date", "August 31, 2026", "2027-08-31"),
  pass("date-11", "start_date", "1st day of September, 2025", "2025-09-01"),
  fail("date-12", "start_date", "2nd day of September, 2025", "2025-09-01"),
  pass("date-13", "start_date", "12 December 2025", "2025-12-12"),
  fail("date-14", "start_date", "December 21, 2025", "2025-12-12"),
];

const OTHER_PAIRS: Pair[] = [
  pass("days-01", "renewal_notice_days", 60, 60),
  pass("days-02", "renewal_notice_days", "60 days", 60),
  fail("days-03", "renewal_notice_days", 3, 60),
  fail("days-04", "renewal_notice_days", "30 days", 60),
  pass("days-05", "late_fee_after_day", 5, 5),
  fail("days-06", "renewal_notice_days", null, 60),
  pass("yes-no-01", "pets_allowed", true, true),
  pass("yes-no-02", "pets_allowed", "yes", true),
  pass("yes-no-03", "sublet_allowed", "No", false),
  fail("yes-no-04", "parking", false, true),
  fail("yes-no-05", "renewal_option", "no", true),
  fail("yes-no-06", "sublet_allowed", "Yes", false),
  pass("text-01", "tenant", "Grace Varga", "Grace Varga"),
  pass("text-02", "tenant", "grace  varga", "Grace Varga"),
  fail("text-03", "tenant", "Grace Vargas", "Grace Varga"),
  pass("text-04", "unit", "2c", "2C"),
  fail("text-05", "unit", "2D", "2C"),
  pass("list-01", "utilities_included", ["water", "trash"], ["trash", "water"]),
  fail("list-02", "utilities_included", [], ["trash"]),
];

// The Python side reads snake_case keys, so these objects are built from [key, value] pairs.
const leaseTerms = (startDate: string, endDate: string, monthlyRent: number) =>
  Object.fromEntries([
    ["start_date", startDate],
    ["end_date", endDate],
    ["monthly_rent", monthlyRent],
  ]);
const rentStep = (effective: string, monthlyRent: number | string) =>
  Object.fromEntries([
    ["effective", effective],
    ["monthly_rent", monthlyRent],
  ]);

const L002 = leaseTerms("2025-01-01", "2026-12-31", 237500);
const L041 = leaseTerms("2025-07-01", "2027-06-30", 165000);
const L111 = leaseTerms("2024-09-01", "2029-08-31", 555000);
const L002_STEPS = [rentStep("2026-01-01", 247000)];
const L041_STEPS = [rentStep("2026-07-01", 171600)];
const L111_STEPS = [
  rentStep("2025-09-01", 571650),
  rentStep("2026-09-01", 588800),
  rentStep("2027-09-01", 606464),
  rentStep("2028-09-01", 624658),
];
const proseSentence = (percent: number) =>
  "On each anniversary of the start date, the monthly rent shall increase by " +
  `${percent}% over the rent then payable, rounded to the nearest cent.`;

const withLease = (pair: Pair, lease: Record<string, unknown>): Pair => ({ ...pair, lease });

const TABLE_STEP_PAIRS: Pair[] = [
  withLease(pass("steps-01", "rent_steps", L111_STEPS, L111_STEPS), L111),
  withLease(pass("steps-02", "rent_steps", [...L111_STEPS].reverse(), L111_STEPS), L111),
  withLease(fail("steps-03", "rent_steps", [], L041_STEPS), L041),
  withLease(
    pass("steps-04", "rent_steps", [rentStep("1 January 2026", "$2,470.00")], L002_STEPS),
    L002,
  ),
  withLease(fail("steps-05", "rent_steps", [rentStep("2026-01-01", 247500)], L002_STEPS), L002),
];

// Prose rent steps must be turned into dated steps before they can be compared.
const PROSE_STEP_PAIRS: Pair[] = [
  withLease(pass("prose-01", "rent_steps", proseSentence(4), L002_STEPS), L002),
  withLease(fail("prose-02", "rent_steps", proseSentence(3), L002_STEPS), L002),
  withLease(pass("prose-03", "rent_steps", proseSentence(4), L041_STEPS), L041),
  withLease(pass("prose-04", "rent_steps", proseSentence(3), L111_STEPS), L111),
  withLease(fail("prose-05", "rent_steps", proseSentence(3), L041_STEPS), L041),
];

const ALL_PAIRS = [
  ...MONEY_PAIRS,
  ...DATE_PAIRS,
  ...OTHER_PAIRS,
  ...TABLE_STEP_PAIRS,
  ...PROSE_STEP_PAIRS,
];

// The pairs are written to a temp file, so the learner's folder never holds the hidden table.
function verdictsFromOneRun(folder: string): Map<string, Verdict> | null {
  const scratch = mkdtempSync(join(tmpdir(), "field-checks-"));
  const pairsPath = join(scratch, "pairs.jsonl");
  const lines = ALL_PAIRS.map(({ right, ...pair }) => JSON.stringify(pair));
  writeFileSync(pairsPath, `${lines.join("\n")}\n`);
  const ran = runPython("checks.py", ["--pairs", pairsPath], folder);
  if (ran.code !== 0) return null;
  const outputLines = ran.out.split("\n").filter((line) => line.trim());
  const verdicts = outputLines.map((line) => JSON.parse(line) as Verdict);
  return new Map(verdicts.map((verdict) => [String(verdict.id), verdict]));
}

const firstRun = once(verdictsFromOneRun);
const secondRun = once(verdictsFromOneRun);
const thirdRun = once(verdictsFromOneRun);

function allRight(folder: string, pairs: Pair[]): boolean {
  const verdicts = firstRun(folder);
  if (!verdicts) return false;
  return pairs.every((pair) => verdicts.get(pair.id)?.verdict === pair.right);
}

function answersEveryPair(folder: string): boolean {
  const verdicts = firstRun(folder);
  if (!verdicts || verdicts.size !== ALL_PAIRS.length) return false;
  return ALL_PAIRS.every((pair) => {
    const verdict = verdicts.get(pair.id);
    const knownVerdict = verdict?.verdict === "pass" || verdict?.verdict === "fail";
    const hasReason = typeof verdict?.reason === "string" && verdict.reason.trim() !== "";
    return knownVerdict && hasReason;
  });
}

function sameVerdictsEveryRun(folder: string): boolean {
  const asText = (verdicts: Map<string, Verdict> | null) =>
    JSON.stringify(ALL_PAIRS.map((pair) => verdicts?.get(pair.id)?.verdict ?? null));
  if (!firstRun(folder)) return false;
  const first = asText(firstRun(folder));
  return first === asText(secondRun(folder)) && first === asText(thirdRun(folder));
}

// The world's own field checks give the accuracy the learner's checks must reach on the golden set.
const EXPECTED_ACCURACY = `
import json, sys
from fernhill.evals import fields
golden = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
rows = [json.loads(line) for line in open("world/data/system_of_record.jsonl")]
written = {row["lease_id"]: row["abstract"] for row in rows}
scores = [fields.score(written[record["lease_id"]], record["abstract"]) for record in golden]
names = scores[0].keys()
per_field = {name: sum(score[name] for score in scores) / len(scores) for name in names}
print(json.dumps({"overall": sum(per_field.values()) / len(per_field), "fields": per_field}))
`;

const ROOT = join(import.meta.dir, "..");

function expectedAccuracy(folder: string): Accuracy | null {
  const golden = join(folder, "golden.jsonl");
  if (!existsSync(golden)) return null;
  const ran = runPython("-c", [EXPECTED_ACCURACY, golden], ROOT);
  return ran.code === 0 ? (JSON.parse(ran.out) as Accuracy) : null;
}

function learnerAccuracy(folder: string): Accuracy | null {
  const scratch = mkdtempSync(join(tmpdir(), "accuracy-"));
  const out = join(scratch, "accuracy.json");
  const ran = runPython("checks.py", ["--golden", "golden.jsonl", "--out", out], folder);
  if (ran.code !== 0 || !existsSync(out)) return null;
  return JSON.parse(readFileSync(out, "utf8")) as Accuracy;
}

const expected = once(expectedAccuracy);
const learner = once(learnerAccuracy);

// Within half a point: 0.005 as a share.
const closeEnough = (got: unknown, want: unknown) =>
  typeof got === "number" && Math.abs(got - Number(want)) <= 0.005;

function accuracyMatches(folder: string): boolean {
  const want = expected(folder);
  const got = learner(folder);
  if (!want || !got || !closeEnough(got.overall, want.overall)) return false;
  const wantFields = Object.entries(want.fields ?? {});
  return wantFields.every(([field, share]) => closeEnough(got.fields?.[field], share));
}

export default [
  {
    says: "checks.py --pairs answers every known pair once, with pass or fail and a reason",
    test: answersEveryPair,
    tryNext:
      "run uv run python checks.py --pairs on a small file of your own; " +
      'print one line of JSON per pair: {"id", "verdict", "reason"}',
  },
  {
    says: "zero wrong verdicts on money",
    test: (folder) => allRight(folder, MONEY_PAIRS),
    tryNext:
      "turn both sides into whole cents with to_cents() before you compare; " +
      '"$2,825.00" and 282500 are the same rent',
  },
  {
    says: "zero wrong verdicts on dates",
    test: (folder) => allRight(folder, DATE_PAIRS),
    tryNext:
      'turn both sides into a date with to_date() first; "1st day of March, 2026" is 2026-03-01',
  },
  {
    says: "day counts, yes or no, text and lists are checked right",
    test: (folder) => allRight(folder, OTHER_PAIRS),
    tryNext:
      'treat "60 days" as 60, "yes" as true, ignore case and extra spaces in names, ' +
      "and ignore the order of a list",
  },
  {
    says: "rent steps in a table match whatever their order and format",
    test: (folder) => allRight(folder, TABLE_STEP_PAIRS),
    tryNext: "sort the steps by date and compare each date and amount after you normalise them",
  },
  {
    says: "prose rent steps are expanded before comparison",
    test: (folder) => allRight(folder, PROSE_STEP_PAIRS),
    tryNext:
      'turn "increase by 4% on each anniversary" into one dated step per anniversary ' +
      "inside the term, rounded to the nearest cent",
  },
  {
    says: "three runs give the same verdicts",
    test: sameVerdictsEveryRun,
    tryNext: "a code check never guesses: remove anything random or time based from checks.py",
  },
  {
    says: "on the golden set, every field's accuracy is within half a point of the world's",
    test: accuracyMatches,
    tryNext:
      "run uv run python checks.py --golden golden.jsonl and compare each field with the " +
      "system of record; write overall and fields as shares from 0 to 1",
  },
] satisfies Rule[];
