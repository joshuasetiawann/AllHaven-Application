# AllHaven Fake Signal Report

## Direct answer

**Did AllHaven ever tell the user something succeeded when it actually did not?**

No false-success toast or completed business operation was confirmed in the tested CRUD, Drive, Knowledge, authentication, or AI-unavailable workflows. Those successful UI actions were checked against API/database state, and unavailable AI/n8n paths reported their limitations honestly.

**Did AllHaven present operational state that was false or internally contradictory?**

Yes—one confirmed fake operational signal was found.

## FS-001 / ALL-001 — System Control misreports Docker services

- **Severity:** HIGH
- **Confidence:** CONFIRMED
- **Claim shown to the user:** `Running 1/3`; Frontend `stopped`; PostgreSQL `stopped`; simultaneously `No services need attention`.
- **Ground truth:** `docker ps` showed the frontend and backend containers up and PostgreSQL up/healthy.
- **Why it is fake:** Fallback service probes target `127.0.0.1` from inside the backend container. Sibling Docker containers do not share that loopback namespace.
- **User impact:** The status page cannot be trusted for diagnosis in this supported deployment shape, and its summary contradicts its own stopped count.
- **Required behavior:** Use deployment-aware observation or label the state `unknown/unobservable`; never translate a failed probe into a definite `stopped` claim unless the probe can observe the target.

## Signals explicitly checked and found honest

| Signal | Underlying proof | Result |
|---|---|---|
| Task/note/finance/calendar/automation/memory mutations | Follow-up API reads, cross-user checks, summary/database behavior, post-delete 404 | HONEST |
| Drive upload/download/delete | Listed metadata, exact downloaded byte count, ownership denial, delete then 404 | HONEST |
| Knowledge indexing/search/reindex/delete | Indexed chunk/search hit, reindex response, delete then 404 | HONEST |
| AI with no provider | Response included `ai_configured:false` and an explicit unavailable message | HONEST |
| n8n unavailable | API/UI exposed not-configured state rather than fabricated workflows | HONEST |
| Wrong local origin | UI reported API unreachable; the underlying cause was CORS, so the failure signal itself was honest | HONEST BUT LOW-DIAGNOSTIC |
| Health endpoint | Matched running backend, version, deployment profile, and DB mode | HONEST for its advertised scope |

## Retest rule

After a fix, stop/restart each container independently and verify both raw API and UI labels. Network/probe failure must produce `unknown`, not `stopped`; the banner must agree with the service counters.
