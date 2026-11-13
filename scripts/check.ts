// bun run check: the repo standard. CI runs this; any failure stops the build.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { allSteps, type Part, parts, ROOT, type Step } from "./structure";

const errors: string[] = [];
const fail = (where: string, what: string) => {
  errors.push(`${relative(ROOT, where) || "."}: ${what}`);
};
const read = (path: string) => readFileSync(path, "utf8");

const STEP_SECTIONS = [
  "## The problem",
  "## Your challenge",
  "## Done when",
  "## If you get stuck",
  "## Words you will use",
];
// Marketing words tell the reader how to feel instead of what the thing does.
const HYPE_WORDS = [
  "supercharge",
  "unleash",
  "unlock",
  "seamless(ly)?",
  "leverage",
  "dive into",
  "game[- ]changer",
  "revolutioni[sz]e",
  "magic(al)?",
  "cutting[- ]edge",
  "AI-powered",
];
const HYPE = new RegExp(`\\b(${HYPE_WORDS.join("|")})\\b`, "i");
const TIME_WORDS = /\b(week|day|hour)\s+\d+\b/i;
const VERB_THING = /^[a-z]+(-[a-z0-9]+)+$/;
const IMAGE = /!\[[^\]]*\]\(([^)\s]+)\)/g;
const MERMAID = /```mermaid\n/;
const MODEL_ID = /\b(claude-[a-z0-9-]+-\d|gpt-\d[\w.-]*|gemini-\d[\w.-]*|o\d-(mini|pro)\b)/i;
const SKIPPED_FOLDERS = new Set(["node_modules", ".git", ".venv", "__pycache__"]);

function walk(folder: string, found: string[] = []): string[] {
  for (const entry of readdirSync(folder)) {
    if (SKIPPED_FOLDERS.has(entry)) continue;
    const path = join(folder, entry);
    if (statSync(path).isDirectory()) walk(path, found);
    else found.push(path);
  }
  return found;
}

const hasImage = (text: string) => [...text.matchAll(IMAGE)].length > 0;

// 1. No Makefile anywhere.
function checkNoMakefile(files: string[]) {
  for (const file of files) {
    if (/(^|\/)(GNU)?[Mm]akefile$/.test(file)) {
      fail(file, "a Makefile is not allowed; use a Bun or uv script");
    }
  }
}

// 2. Prose rules on every Markdown file.
function checkProseLine(file: string, line: string, lineNumber: number) {
  const where = `line ${lineNumber}`;
  if (line.includes("—")) fail(file, `${where}: em dash`);
  const hype = line.match(HYPE);
  if (hype) fail(file, `${where}: hype word "${hype[0]}"`);
  const timeWord = line.match(TIME_WORDS);
  // Only the schedules may talk about time; the parts hold content.
  if (timeWord && !file.includes("schedules")) {
    fail(file, `${where}: "${timeWord[0]}"; content is in parts, schedules map time`);
  }
  if (/\bM=\d+|verify \d+/.test(line)) fail(file, `${where}: numeric step command; name the step`);
}

function checkProse(markdownFiles: string[]) {
  for (const file of markdownFiles) {
    const lines = read(file).split("\n");
    lines.forEach((line, index) => {
      checkProseLine(file, line, index + 1);
    });
  }
}

// 2b. Every page shows, not only tells: images it names exist, and the key pages carry a picture.
function checkImagesExist(markdownFiles: string[]) {
  for (const file of markdownFiles) {
    for (const match of read(file).matchAll(IMAGE)) {
      const image = match[1];
      if (/^https?:/.test(image)) continue;
      if (!existsSync(join(dirname(file), image))) fail(file, `image "${image}" does not exist`);
    }
  }
}

type Picture = { file: string; what: string; mermaid: boolean; image: boolean };

function needPicture({ file, what, mermaid, image }: Picture) {
  if (!existsSync(file)) return fail(file, "missing");
  const text = read(file);
  if (mermaid && !MERMAID.test(text)) fail(file, `${what} needs a Mermaid diagram`);
  if (image && !hasImage(text)) fail(file, `${what} needs a screenshot`);
}

function checkKeyPictures() {
  const rootReadme = join(ROOT, "README.md");
  needPicture({ file: rootReadme, what: "the root README", mermaid: true, image: true });
  const orientation = join(ROOT, "00-orientation", "README.md");
  needPicture({ file: orientation, what: "the orientation", mermaid: false, image: true });
}

// 3. Parts and steps.
function checkPartReadme(part: Part) {
  const readme = join(part.dir, "README.md");
  if (!existsSync(readme)) return fail(part.dir, "part has no README.md");
  const text = read(readme);
  if (!MERMAID.test(text)) fail(readme, "part README needs a Mermaid diagram");
  const walkthrough = text.split("## Walkthrough")[1]?.split("\n## ")[0];
  if (walkthrough === undefined) {
    fail(readme, `part README needs a "## Walkthrough" section`);
  } else if (!walkthrough.includes("```bash")) {
    fail(readme, "the walkthrough needs the commands, each with an Expect: line");
  }
}

function checkStepNameAndSize(step: Step, seen: Set<string>) {
  if (!VERB_THING.test(step.name)) {
    fail(step.dir, `step name "${step.name}" must be verb-thing in lower case`);
  }
  if (seen.has(step.name)) fail(step.dir, `step name "${step.name}" is used twice`);
  seen.add(step.name);
  if (!existsSync(join(step.dir, "step.toml"))) fail(step.dir, "missing step.toml");
  const minutes = step.meta.minutes;
  if (minutes < 5 || minutes > 30) {
    fail(step.dir, `step is ${minutes} min; keep a step between 5 and 30, split it if longer`);
  }
}

function checkStepReadme(readme: string, text: string) {
  const words = text.split(/\s+/).filter(Boolean).length;
  if (words > 600) fail(readme, `${words} words; a step README stays under 600, split the step`);
  for (const heading of STEP_SECTIONS) {
    if (!text.includes(heading)) fail(readme, `missing section "${heading}"`);
  }
  if (!MERMAID.test(text) && !hasImage(text)) {
    fail(readme, "a step shows a picture: a screenshot or a Mermaid diagram");
  }
  const doneWhen = text.split("## Done when")[1]?.split("\n## ")[0] ?? "";
  if (!/^- /m.test(doneWhen)) fail(readme, "Done when needs at least one bullet");
}

function checkStepFiles(step: Step, readme: string, text: string) {
  if (step.meta.screen) {
    const expected = join(step.dir, "images", "expected.png");
    if (!existsSync(expected)) fail(step.dir, "screen step needs images/expected.png");
    if (!text.includes("images/expected.png")) {
      fail(readme, "screen step must show ../images/expected.png");
    }
  }
  if (step.meta.solution && !existsSync(join(step.dir, "solution"))) {
    fail(step.dir, "step.toml says solution but there is no solution/");
  }
  const checks = join(ROOT, "checks");
  const hasCheck =
    existsSync(join(checks, `${step.name}.ts`)) || existsSync(join(checks, `${step.name}.py`));
  if (!hasCheck) fail(step.dir, `no check at checks/${step.name}.ts`);
}

function checkStep(step: Step, seen: Set<string>) {
  checkStepNameAndSize(step, seen);
  const readme = join(step.dir, "problem", "README.md");
  if (!existsSync(readme)) return fail(step.dir, "missing problem/README.md");
  const text = read(readme);
  checkStepReadme(readme, text);
  checkStepFiles(step, readme, text);
}

function checkParts(allParts: Part[]) {
  const seen = new Set<string>();
  if (allParts.length === 0) fail(join(ROOT, "parts"), "no parts");
  for (const part of allParts) {
    checkPartReadme(part);
    if (part.steps.length === 0) fail(part.dir, "part has no steps");
    for (const step of part.steps) checkStep(step, seen);
  }
}

// 4. Commands: the README runs the finished system first,
// and every command block says what to expect.
function checkRootReadmeOrder() {
  const rootReadme = join(ROOT, "README.md");
  if (!existsSync(rootReadme)) return fail(ROOT, "missing README.md");
  const text = read(rootReadme);
  const firstCode = text.indexOf("```bash");
  const firstConcept = text.search(/^## (How it works|Concepts|Background|Why)/m);
  if (firstCode < 0) {
    fail(rootReadme, "the README needs a bash block that runs the finished system");
  } else if (firstConcept >= 0 && firstConcept < firstCode) {
    fail(rootReadme, "run the finished system before any concept section");
  }
}

function checkExpectLines(file: string) {
  const lines = read(file).split("\n");
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() !== "```bash") continue;
    let j = i + 1;
    while (j < lines.length && lines[j].trim() !== "```") j++;
    const after = lines.slice(j + 1).find((line) => line.trim() !== "");
    if (!after?.startsWith("Expect:")) {
      fail(file, `line ${i + 1}: a bash block must be followed by an Expect: line`);
    }
    i = j;
  }
}

// 5. One model config, exact pins, a troubleshooting table.
function checkModelIds(files: string[]) {
  const searched = files.filter(
    (file) =>
      /\.(ts|py|md|json|toml|ya?ml)$/.test(file) &&
      !file.includes("/config/models.") &&
      !file.includes("/scripts/check.ts"),
  );
  for (const file of searched) {
    const model = read(file).match(MODEL_ID);
    if (model) fail(file, `model id "${model[0]}" outside config/models; name models in one place`);
  }
}

type PackageJson = {
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
};

const EXACT_VERSION = /^\d+\.\d+\.\d+$/;
// A Python requirement with a range instead of ==, such as "litellm>=1.0".
const PYTHON_RANGE = /"([A-Za-z0-9_.\-[\]]+)\s*(>=|~=|\^|>|<)[^"]*"/g;

function checkPackagePins() {
  const packagePath = join(ROOT, "package.json");
  if (!existsSync(packagePath)) return;
  const packageJson = JSON.parse(read(packagePath)) as PackageJson;
  const versions = { ...packageJson.dependencies, ...packageJson.devDependencies };
  for (const [name, version] of Object.entries(versions)) {
    if (!EXACT_VERSION.test(version)) fail(packagePath, `${name}@${version}: pin an exact version`);
  }
}

function checkPythonPins() {
  const pyproject = join(ROOT, "pyproject.toml");
  if (!existsSync(pyproject)) return;
  for (const match of read(pyproject).matchAll(PYTHON_RANGE)) {
    fail(pyproject, `${match[1]}: pin with == not ${match[2]}`);
  }
}

function checkTroubleshooting() {
  const trouble = join(ROOT, "00-orientation", "troubleshooting.md");
  const table = /\| *What you see *\| *What it means *\| *Fix *\|/;
  if (!existsSync(trouble) || !table.test(read(trouble))) {
    fail(
      ROOT,
      "00-orientation/troubleshooting.md needs a table: What you see | What it means | Fix",
    );
  }
}

// 6. Every schedule covers every part, and the minutes add up.
type Session = { parts: string[]; minutes: number };
type Schedule = { sessions: Session[] };
type Schedules = Record<string, Schedule>;

function minutesPerPart(allParts: Part[]): Record<string, number> {
  const pairs = allParts.map((part) => {
    const minutes = part.steps.reduce((total, step) => total + step.meta.minutes, 0);
    return [part.name, minutes];
  });
  return Object.fromEntries(pairs);
}

type ScheduleCheck = { schedulePath: string; format: string; schedule: Schedule };

function checkScheduleCoversParts(check: ScheduleCheck & { allParts: Part[] }) {
  const listed = check.schedule.sessions.flatMap((session) => session.parts);
  for (const part of check.allParts) {
    if (!listed.includes(part.name)) {
      fail(check.schedulePath, `${check.format} leaves out part "${part.name}"`);
    }
  }
}

function checkSessionMinutes(check: ScheduleCheck & { partMinutes: Record<string, number> }) {
  for (const session of check.schedule.sessions) {
    const need = session.parts.reduce((total, name) => total + (check.partMinutes[name] ?? 0), 0);
    if (need > session.minutes) {
      const what = `a session needs ${need} min but has ${session.minutes}`;
      fail(check.schedulePath, `${check.format}: ${what}`);
    }
  }
}

function checkSchedules(allParts: Part[]) {
  const schedulePath = join(ROOT, "schedules.toml");
  if (!existsSync(schedulePath)) return fail(ROOT, "missing schedules.toml");
  const schedules = Bun.TOML.parse(read(schedulePath)) as Schedules;
  const partMinutes = minutesPerPart(allParts);
  for (const [format, schedule] of Object.entries(schedules)) {
    checkScheduleCoversParts({ schedulePath, format, schedule, allParts });
    checkSessionMinutes({ schedulePath, format, schedule, partMinutes });
  }
}

const files = walk(ROOT);
const markdownFiles = files.filter((file) => file.endsWith(".md"));
const allParts = parts();

checkNoMakefile(files);
checkProse(markdownFiles);
checkImagesExist(markdownFiles);
checkKeyPictures();
checkParts(allParts);
checkRootReadmeOrder();
for (const file of markdownFiles) checkExpectLines(file);
checkModelIds(files);
checkPackagePins();
checkPythonPins();
checkTroubleshooting();
checkSchedules(allParts);

if (errors.length) {
  console.log(`The repo does not meet the standard. ${errors.length} problem(s):`);
  for (const error of errors) console.log(`  - ${error}`);
  process.exit(1);
}
console.log(
  `The repo meets the standard: ${allParts.length} part(s), ${allSteps().length} step(s).`,
);
