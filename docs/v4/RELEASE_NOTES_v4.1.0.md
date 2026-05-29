# AllHaven v4.1.0 - Release Notes

Date: 2026-06-27

AllHaven 4.1.0 is a focused repair release for the places that felt broken in daily use: finance charts, Notes editing, and AI Memory quality.

## Fixed

- Dashboard and Finance cashflow charts now render visible bars with a stable baseline and an honest empty-period state.
- Existing Notes can now be edited from the Notes reader panel, then saved without losing the selected note.
- Clearing a note's content now persists correctly instead of being ignored.
- AI Memory now treats relationship facts like "pacar saya Kelly" as a stable, replaceable profile fact.
- AI Memory no longer auto-learns noisy insult-like statements from normal chat.
- Memory context now keeps the newest single-value profile fact for name, partner, friend, school, and location so old contradictory facts do not confuse the model.

## Security

- Next.js is updated to 15.5.19 to clear current npm advisory findings.
- Local CORS no longer echoes arbitrary public origins by default; it allows localhost, private LAN IPs, Tailscale 100.x IPs, Tailscale Serve `.ts.net` hosts, and the Capacitor app origin.

## Verification

- `npm audit --audit-level=low` -> 0 vulnerabilities
- `npm run build` -> success
- `pytest backend/tests/test_ai_intent_finance.py backend/tests/test_ai_chat_memory.py backend/tests/test_memory_context_builder.py` -> 58 passed
- `pytest backend/tests/test_ai_tool_execution.py backend/tests/test_proposal_dedup.py backend/tests/test_ai_intent_finance.py` -> 45 passed
- `pytest backend/tests/test_cors.py` -> 2 passed
