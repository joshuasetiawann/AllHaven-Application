// Cross-platform npm entrypoint for Haven. `npm run setup` installs & starts
// Haven from THIS terminal (no website); `npm run start` just opens the app.
// It resolves Python 3 (python3 → python) and runs the matching installer
// script, inheriting stdio so the terminal is the only surface.
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
// setup = terminal installer (default); start = ensure+open; web = optional browser wizard.
const targets = { setup: "haven_cli.py", start: "haven_launch.py", web: "haven_setup.py" };
const which = process.argv[2] || "setup";
const script = path.join(__dirname, targets[which] || targets.setup);

const result = spawnSync(python, [script], { stdio: "inherit" });
if (result.error) {
  console.error("Could not start Python. Install Python 3 from https://www.python.org/downloads/");
  process.exit(1);
}
process.exit(result.status === null ? 1 : result.status);
