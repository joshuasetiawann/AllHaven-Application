# AllHaven Command Center — Version Archive

This repository keeps **every version of the project as its own self-contained folder**,
oldest → newest. Each `V<n>/` is a full snapshot you can open and run on its own.

| Version | Folder | What it is |
|--------:|--------|------------|
| V1 … V13 | `V1/CORE-OS-APPLICATION-` … `V13/CORE-OS-APPLICATION-` | **CoreOS Command Center era** — progressive snapshots, from the earliest build (V1) to the most complete CoreOS-era version (V13). |
| **V14 (current)** | `V14/AllHaven-Application` | **AllHaven** — the rebrand + everything since: 9 AI providers, parallel multi-agent chat, **multi-agent Debate**, and the **Reasoning Quality Layer** (Analyst → Critic → Synthesizer). Semantic version **v0.3.0**. |

## Run the current version

```bash
cd V14/AllHaven-Application
# follow its README / docs/LOCAL_SETUP.md
./allhaven.sh        # one-command setup + run (Linux/macOS)
```

The current version keeps its own detailed history inside the folder:
`V14/AllHaven-Application/CHANGELOG.md`, `VERSION`, and `docs/releases/`.

## How versioning works here

- Folders are numbered `V1, V2, …` from oldest to newest.
- A new **big update adds the next folder** (`V15`, `V16`, …) — the previous
  versions stay frozen so you always have the full history side by side.
- Inside the latest version folder, semantic versioning (`MAJOR.MINOR.PATCH`) and
  a changelog track finer-grained changes (see `V14/AllHaven-Application/docs/VERSIONING.md`).
