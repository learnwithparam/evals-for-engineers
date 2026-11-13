import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { DATA, type JsonRecord, readJsonl, splits } from "./lib/world";

// The learner writes golden.jsonl, so every field may be missing or have the wrong type.
type GoldenRecord = { abstract?: unknown; [field: string]: unknown };
// Keys such as lease_type come from the Python side, so they are read by name.
type Lease = { id: string; amendments: number; [field: string]: unknown };
type AnswerKey = { abstract: JsonRecord; [field: string]: unknown };

const REQUIRED_CRITICAL_FIELDS = ["monthly_rent", "renewal_notice_days"];
const ABSTRACT_FIELDS = [
  "unit",
  "tenant",
  "lease_type",
  "start_date",
  "end_date",
  "monthly_rent",
  "rent_steps",
  "deposit",
  "renewal_option",
  "renewal_notice_days",
  "pets_allowed",
  "pet_fee",
  "late_fee",
  "late_fee_after_day",
  "early_termination_fee",
  "utilities_included",
  "parking",
  "sublet_allowed",
];

function golden(folder: string): GoldenRecord[] {
  const path = join(folder, "golden.jsonl");
  if (!existsSync(path)) return [];
  return readJsonl<GoldenRecord>(path);
}

const leaseIds = (folder: string) => golden(folder).map((record) => String(record.lease_id));

function leasesById(): Map<string, Lease> {
  const leases = readJsonl<Lease>(join(DATA, "leases.jsonl"));
  return new Map(leases.map((lease) => [lease.id, lease]));
}

function approvedAbstracts(): Map<string, JsonRecord> {
  const keys = readJsonl<AnswerKey>(join(DATA, "keys.jsonl"));
  return new Map(keys.map((key) => [String(key.lease_id), key.abstract]));
}

// Two abstracts are the same when every field holds the same value, whatever the key order.
function sameAbstract(written: unknown, approved: JsonRecord | undefined): boolean {
  if (!approved || typeof written !== "object" || written === null) return false;
  const writtenAbstract = written as JsonRecord;
  return ABSTRACT_FIELDS.every(
    (field) => JSON.stringify(writtenAbstract[field]) === JSON.stringify(approved[field]),
  );
}

function countLeases(folder: string, matches: (lease: Lease) => boolean): number {
  const leases = leasesById();
  const known = leaseIds(folder).filter((id) => leases.has(id));
  return known.filter((id) => matches(leases.get(id) as Lease)).length;
}

function criticalFieldsAreRight(record: GoldenRecord): boolean {
  const fields = record.critical_fields;
  if (!Array.isArray(fields)) return false;
  const allReal = fields.every((field) => ABSTRACT_FIELDS.includes(field));
  const hasRequired = REQUIRED_CRITICAL_FIELDS.every((field) => fields.includes(field));
  return allReal && hasRequired;
}

export default [
  {
    says: "golden.jsonl holds 40 records",
    test: (folder) => golden(folder).length === 40,
    tryNext: "run uv run python build_golden.py; golden_records() must return 40 records",
  },
  {
    says: "every record is a different, real lease",
    test: (folder) => {
      const ids = leaseIds(folder);
      const leases = leasesById();
      const unique = new Set(ids).size === ids.length;
      return ids.length > 0 && unique && ids.every((id) => leases.has(id));
    },
    tryNext: "use lease ids from world/data/keys.jsonl, such as L005, and never repeat one",
  },
  {
    says: "no lease comes from the gate set",
    test: (folder) => {
      const gate = new Set(splits().gate);
      const ids = leaseIds(folder);
      return ids.length > 0 && ids.every((id) => !gate.has(id));
    },
    tryNext:
      'leave out every lease in splits["gate"]: Gate the change tests releases on those 50 leases',
  },
  {
    says: "at least 10 amended leases",
    test: (folder) => countLeases(folder, (lease) => lease.amendments > 0) >= 10,
    tryNext: "amended leases are where the abstractor misses the rent, so take at least 10 of them",
  },
  {
    says: "at least 3 commercial leases",
    test: (folder) => countLeases(folder, (lease) => lease.lease_type === "commercial") >= 3,
    tryNext: "take at least 3 leases whose lease_type is commercial; they have 4 rent steps each",
  },
  {
    says: "every abstract is the approved one from the answer keys",
    test: (folder) => {
      const approved = approvedAbstracts();
      const records = golden(folder);
      const allSame = records.every((record) =>
        sameAbstract(record.abstract, approved.get(String(record.lease_id))),
      );
      return records.length > 0 && allSame;
    },
    tryNext:
      "copy each abstract from world/data/keys.jsonl; " +
      "the system of record holds the abstractor's output, which you are testing",
  },
  {
    says: "critical_fields names real fields, with monthly_rent and renewal_notice_days",
    test: (folder) => {
      const records = golden(folder);
      return records.length > 0 && records.every(criticalFieldsAreRight);
    },
    tryNext:
      'give every record "critical_fields": ["monthly_rent", "rent_steps", "deposit", ' +
      '"renewal_notice_days"]',
  },
] satisfies Rule[];
