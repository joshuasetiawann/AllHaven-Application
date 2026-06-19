// Cross-platform npm entrypoint for Haven. `npm run setup` / `npm run start`
// resolve Python 3 (python3 → python) and run the matching installer script,
// inheriting stdio so the terminal acts purely as a bootstrapper. The Setup
// Wizard opens in the browser; the terminal is not where you configure Haven.
"use strict";

const { spawnSync } = require("child_process");
const path = require("path");

function hasCmd(cmd) {
  const probe = process.platform === "win32" ? "where" : "command";
  const args = process.platform === "win32" ? [cmd] : ["-v", cmd];
  try {
    return spawnSync(probe, args, { stdio: "ignore", shell: process.platform !== "win32" }).status === 0;
  } catch {
    return false;
  }
}

const python = hasCmd("python3") ? "python3" : "python";
const targets = { setup: "haven_setup.py", start: "haven_launch.py", cli: "haven_cli.py" };
const which = process.argv[2] || "setup";
const script = path.join(__dirname, targets[which] || targets.setup);

const result = spawnSync(python, [script], { stdio: "inherit" });
if (result.error) {
  console.error("Could not start Python. Install Python 3 from https://www.python.org/downloads/");
  process.exit(1);
}
process.exit(result.status === null ? 1 : result.status);
