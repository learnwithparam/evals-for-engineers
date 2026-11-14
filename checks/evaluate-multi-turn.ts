import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { type JsonRecord, readJsonl } from "./lib/world";

type Conversation = { id: string; turns: boolean[]; [field: string]: unknown };

const RATE_TOLERANCE = 0.005;

// Two lists hold the same ids when they match once both are sorted.
function sameIds(left: unknown[], right: unknown[]): boolean {
  const sortedLeft = [...left].sort();
  const sortedRight = [...right].sort();
  return JSON.stringify(sortedLeft) === JSON.stringify(sortedRight);
}

const conversations = (folder: string) =>
  readJsonl<Conversation>(join(folder, "conversations.jsonl"));

function summary(folder: string): JsonRecord {
  const path = join(folder, "multi_turn.json");
  return existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : {};
}

const share = (count: number, total: number) => count / total;

function near(written: unknown, wanted: number): boolean {
  return typeof written === "number" && Math.abs(written - wanted) <= RATE_TOLERANCE;
}

const hasMiss = (conversation: Conversation) => conversation.turns.includes(false);

function firstFailCounts(folder: string): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const conversation of conversations(folder).filter(hasMiss)) {
    const turn = String(conversation.turns.indexOf(false) + 1);
    counts[turn] = (counts[turn] ?? 0) + 1;
  }
  return counts;
}

export default [
  {
    says: "multi_turn.json has the five fields",
    test: (folder) =>
      ["goal_rate", "all_turns_rate", "per_turn_rate", "first_fail_turns", "recovered"].every(
        (field) => field in summary(folder),
      ),
    tryNext: "run uv run python multi_turn.py; it writes multi_turn.json for you",
  },
  {
    says: "goal_rate is the share of conversations that met the goal",
    test: (folder) => {
      const rows = conversations(folder);
      const met = rows.filter((row) => row.goal_met === true).length;
      return near(summary(folder).goal_rate, share(met, rows.length));
    },
    tryNext: "count conversations with goal_met true, not turns; divide by all conversations",
  },
  {
    says: "all_turns_rate is the share of conversations with every turn right",
    test: (folder) => {
      const rows = conversations(folder);
      const clean = rows.filter((row) => !hasMiss(row)).length;
      return near(summary(folder).all_turns_rate, share(clean, rows.length));
    },
    tryNext: "a conversation counts only when no turn in it is false",
  },
  {
    says: "per_turn_rate is the share of single turns that were right",
    test: (folder) => {
      const turns = conversations(folder).flatMap((row) => row.turns);
      return near(summary(folder).per_turn_rate, share(turns.filter(Boolean).length, turns.length));
    },
    tryNext: "flatten every turn of every conversation, then count the true ones",
  },
  {
    says: "first_fail_turns counts conversations by the turn where they first broke",
    test: (folder) => {
      const written = summary(folder).first_fail_turns;
      return JSON.stringify(written) === JSON.stringify(firstFailCounts(folder));
    },
    tryNext: 'count from 1; the keys are strings such as "2", and only failing chats are counted',
  },
  {
    says: "recovered lists the chats that missed a turn and still met the goal",
    test: (folder) => {
      const written = summary(folder).recovered;
      const wanted = conversations(folder)
        .filter((row) => row.goal_met === true && hasMiss(row))
        .map((row) => row.id)
        .sort();
      return Array.isArray(written) && sameIds(written, wanted);
    },
    tryNext: "keep a conversation when goal_met is true and at least one turn is false",
  },
] satisfies Rule[];
