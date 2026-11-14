import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { DATA, readJsonl } from "./lib/world";

type Synthetic = {
  id?: unknown;
  source?: unknown;
  topic?: unknown;
  tone?: unknown;
  lease_type?: unknown;
  question?: unknown;
  reviewed?: unknown;
};

const TOPICS = ["late", "pets", "renewal", "rent"];
const TONES = ["formal", "rushed", "vague"];
const LEASE_TYPES = ["residential", "commercial"];
const MINIMUM_CASES = 12;
const MINIMUM_COMBINATIONS = 8;
const MINIMUM_WORDS = 5;

function cases(folder: string): Synthetic[] {
  const path = join(folder, "synthetic.jsonl");
  return existsSync(path) ? readJsonl<Synthetic>(path) : [];
}

const questionOf = (row: Synthetic) => String(row.question ?? "").trim();
const normal = (text: string) => text.toLowerCase().replace(/\s+/g, " ");

// Seed questions and the real staff questions are not new, so copying them proves nothing.
function knownQuestions(folder: string): Set<string> {
  const seeds = readJsonl<{ question: string }>(join(folder, "seed_questions.jsonl"));
  const staff = readJsonl<{ question: string }>(join(DATA, "questions.jsonl"));
  return new Set([...seeds, ...staff].map((row) => normal(row.question)));
}

export default [
  {
    says: "synthetic.jsonl holds at least 12 cases",
    test: (folder) => cases(folder).length >= MINIMUM_CASES,
    tryNext: "write 12 or more lines in synthetic.jsonl, one JSON object per case",
  },
  {
    says: "every case is tagged synthetic, has a unique id and was reviewed by a person",
    test: (folder) => {
      const rows = cases(folder);
      const ids = new Set(rows.map((row) => row.id));
      const tagged = rows.every((row) => row.source === "synthetic" && row.reviewed === true);
      return rows.length > 0 && tagged && ids.size === rows.length;
    },
    tryNext: 'give every case "source": "synthetic", "reviewed": true after you read it, and a new id',
  },
  {
    says: "every case names a topic, a tone and a lease type from the lists",
    test: (folder) => {
      const rows = cases(folder);
      const valid = (row: Synthetic) =>
        TOPICS.includes(String(row.topic)) &&
        TONES.includes(String(row.tone)) &&
        LEASE_TYPES.includes(String(row.lease_type));
      return rows.length > 0 && rows.every(valid);
    },
    tryNext: "topic is late, pets, renewal or rent; tone is formal, rushed or vague",
  },
  {
    says: "every topic, tone and lease type is used at least once",
    test: (folder) => {
      const rows = cases(folder);
      const used = (field: "topic" | "tone" | "lease_type", values: string[]) =>
        values.every((value) => rows.some((row) => row[field] === value));
      return used("topic", TOPICS) && used("tone", TONES) && used("lease_type", LEASE_TYPES);
    },
    tryNext: "a set with one tone or one topic only tests one slice; cover every value in each list",
  },
  {
    says: "the cases cover at least 8 different topic, tone and lease type mixes",
    test: (folder) => {
      const mixes = cases(folder).map((row) => `${row.topic}/${row.tone}/${row.lease_type}`);
      return new Set(mixes).size >= MINIMUM_COMBINATIONS;
    },
    tryNext: "change two dimensions at once, such as a rushed tenant on a commercial lease",
  },
  {
    says: "every question is new, with at least 5 words and no repeats",
    test: (folder) => {
      const known = knownQuestions(folder);
      const questions = cases(folder).map((row) => normal(questionOf(row)));
      const long = questions.every((text) => text.split(" ").length >= MINIMUM_WORDS);
      const fresh = questions.every((text) => !known.has(text));
      return questions.length > 0 && long && fresh && new Set(questions).size === questions.length;
    },
    tryNext: "write each question yourself from its dimensions; do not copy a seed or a staff question",
  },
] satisfies Rule[];
