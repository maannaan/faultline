# Faultline demo script

Record about two minutes. Start from a seeded graph: `make reset`, `make seed`, `make api`, `make web`. The scored answers below come from the deterministic snapshot rules. Groq may phrase a live note, and a wording miss does not change the evidence.

## 0:00–0:15 Problem

Stay on the timeline at http://127.0.0.1:3010 before selecting a cutoff.

Say: "An agent can repeat a deploy region that was already corrected, and the next agent never sees that the on-call owner is still disputed."

## 0:15–0:40 Timeline

Select Project Atlas. Leave the cutoff empty so the board shows status now.

Say: "region-b is current and cites the change record. region-a is superseded. Priya and Jordan are both disputed."

## 0:40–1:05 Two cutoffs

Set the cutoff to 15 Oct 2026, 17:30 local, which is `2026-10-15T12:00:00Z`. Show cutoff.

Say: "At that moment only region-a was known, and it was current. region-b did not exist yet."

Set the cutoff to 16 Oct 2026, 18:30 local, which is `2026-10-16T13:00:00Z`. Show cutoff.

Say: "By the next afternoon region-b is current because it supersedes region-a. The on-call pair is still unresolved."

## 1:05–1:30 Replay Lab

Open http://127.0.0.1:3010/replay. Keep the rollout question and `deploy_region`. Run replay.

Say: "The same question cites region-a on the early snapshot and region-b on the late one. The diff names assert-region-b SUPERSEDES assert-region-a."

Check "Exclude source-change-002" and run again.

Say: "Without that source, the candidate snapshot falls back to region-a. The exclusion is a filter. The edge is still in the graph."

## 1:30–1:50 Conflict and handoff

Change the predicate to `oncall_owner` and run replay on the late cutoff.

Say: "Faultline does not pick Priya or Jordan. The claim is disputed."

Open http://127.0.0.1:3010/handoff. Create the handoff with both memory refs. Accept as agent-release.

Say: "The release agent receives region-b and still sees both on-call assertions. The client cannot drop that dispute."

Optional, if time remains: restart FalkorDB with `docker compose restart falkordb`, reload the handoff page's last task only if you still have its id, or reload the timeline. Say: "The graph is FalkorDB. A restart keeps the assertions."

## 1:50–2:05 Ablation

Open http://127.0.0.1:3010/bench. Click "Run ablation".

Say: "Deleting the SUPPORTED_BY edge removes region-b from the answer. Deleting SUPERSEDES leaves both regions current, and Faultline refuses to choose. Both edges are restored."

Point at the restored badge. Stop.
