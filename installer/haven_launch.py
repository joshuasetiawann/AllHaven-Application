"""Haven launch helper — "ensure services running, then open the app".

This is what the desktop shortcut (and START_HAVEN_* after first-time setup)
runs. It is intentionally small and safe:
    * makes sure the localhost Haven agent is running (starts it if not),
    * asks the agent to start Postgres (Docker), the backend, and the frontend,
    * waits for the frontend port, then opens the browser.

It never runs shell commands or destructive Docker operations itself — all
control goes through the token-gated agent. Stdlib only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import haven_common as hc  # noqa: E402


def _agent_ping() -> bool:
    try:
        with urllib.request.urlopen(f"{hc.agent_base_url()}/ping", timeout=2) as r:  # noqa: S310
            return r.status == 200
    except OSError:
        return False


def _agent_post(path: str, timeout: float = 130.0) -> tuple[int, dict]:
    token = hc.read_token() or ""
    req = urllib.request.Request(
        f"{hc.agent_base_url()}{path}", data=b"{}", method="POST",
        headers={"X-Haven-Token": token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed localhost)
        return r.status, json.loads(r.read().decode("utf-8") or "{}")


def ensure_agent() -> bool:
    if _agent_ping():
        return True
    hc.ensure_dirs()
    hc.ensure_token()
    log = open(hc.logs_dir() / "agent.log", "ab")  # noqa: SIM115
    kwargs: dict = {"stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL,
                    "cwd": str(hc.repo_root())}
    if os.name == "posix":
        kwargs["start_new_session"] = True
    else:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([hc.venv_python(), str(hc.repo_root() / "installer" / "haven_agent.py")], **kwargs)  # noqa: S603
    for _ in range(24):
        if _agent_ping():
            return True
        time.sleep(0.5)
    return False


def main() -> int:
    hc.ensure_dirs()
    print("Starting Haven…")
    if not ensure_agent():
        print("Could not start the Haven control agent. See var/logs/agent.log for details.")
        return 1

    for name in ("postgres", "backend", "frontend"):
        try:
            _, body = _agent_post(f"/service/{name}/start")
            print(f"  {name}: {body.get('message', 'ok')}")
        except OSError as exc:
            print(f"  {name}: could not start ({hc.mask_secrets(str(exc))})")

    env = hc.read_env()
    fe_port = int(env.get("FRONTEND_PORT") or hc.default_port("frontend") or 3000)
    url = f"http://localhost:{fe_port}"

    print(f"Waiting for the app to be ready at {url} …")
    deadline = time.time() + 90
    while time.time() < deadline:
        if hc.port_in_use(fe_port):
            break
        time.sleep(1)

    print(f"Opening {url}")
    try:
        webbrowser.open(url)
    except OSError:
        print(f"Open this address in your browser: {url}")
    print("Haven is running. You can close this window; services keep running in the background.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
