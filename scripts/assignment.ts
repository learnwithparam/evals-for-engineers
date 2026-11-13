// Proves the assignment check: it passes on the reference solution and fails on the starter.
import { join } from "node:path";
import { ROOT } from "./structure";

function runCheck(folder: string): number {
  const command = ["uv", "run", "--quiet", "checks/assignment.py", "--dir", folder];
  const finished = Bun.spawnSync(command, { cwd: ROOT, stdout: "inherit", stderr: "inherit" });
  return finished.exitCode ?? -1;
}

const solution = join(ROOT, "parts/07-do-it-with-the-tools-teams-run/01-port-the-gate/solution");
console.log("Assignment check on the reference solution (must pass):");
const solutionCode = runCheck(solution);
console.log("Assignment check on the untouched starter (must fail):");
const starterCode = runCheck(join(ROOT, "assignment"));

if (solutionCode !== 0 || starterCode === 0) {
  console.log("The assignment check does not tell the solution from the starter.");
  process.exit(1);
}
console.log("The assignment check passes on the solution and fails on the starter.");
