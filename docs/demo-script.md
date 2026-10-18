# Faultline demo video script (2:30–3:00)

Record on the live site, **https://faultline.mannnan.com**, in a desktop browser at about 1440×900, with dark UI and no extensions visible. Every answer shown comes from the production FalkorDB graph and the deterministic policy. No LLM is needed for any of it.

**Before you record:**
- Open these tabs in order:
  1. landing `/`
  2. `/app/timeline`
  3. `/app/replay`
  4. `/app/blame`
  5. `/app/bisect`
  6. `/app/impact`
  7. `/app/handoff`
  8. `/app/bench`
  9. the GitHub Actions page `github.com/maannaan/faultline/actions`
- Wait for the "FalkorDB connected" pill on an app page.
- Speak slowly. Each section has a click list and one or two sentences to say.

---

## 0:00–0:15 · Hook (landing page)

Show the landing hero and let the animated graph play one loop.

> "Agents change their answers, and nobody can say why. Developers have git blame, diff and bisect for code. Faultline is git for agent memory, built on FalkorDB."

Scroll once so the terminal strip starts typing, then stop.

## 0:15–0:45 · `checkout`: the Time Machine (`/app/timeline`)

Click **Replay history** under the Evidence Graph and let it play from "before" to "now".

> "Every node is a FalkorDB record: agent, session, memory event, assertion, source. As I move through time, statuses are recomputed from the edges visible at that moment. On the 15th, region-a is current. On the 16th, a reviewed change record arrives. The SUPERSEDES edge turns region-a grey, and two on-call sources disagree, so Priya and Jordan are both disputed."

Click the `region-b` node to open the evidence sheet for a second.

## 0:45–1:10 · `diff`: the Replay Lab (`/app/replay`)

Click **Run replay** with the defaults.

> "Same question, two snapshots. Region-a on the 15th, region-b on the 16th. The diff is computed from graph ids, not wording, and it names the edge: assert-region-b SUPERSEDES assert-region-a."

Tick **Counterfactual** and click **Run replay** again.

> "Exclude the change record and the answer falls back to region-a. It's a filter; nothing is deleted."

## 1:10–1:25 · `blame` (`/app/blame`)

Click **Ask: Region · 16 Oct**.

> "Blame follows the answer edge by edge: claim, assertion, the reviewed source, the memory event, the session, and the agent that recorded it."

## 1:25–1:50 · `bisect` (`/app/bisect`)

Click **Run bisect** (deploy_region, good on 15 Oct, bad on 16 Oct). Let the log animate.

> "The answer was right on the 15th and different on the 16th. Bisect binary-searches the recorded memory with as-of queries and names the culprit: source-change-002, event evt-assert-region-b."

Switch the question to `oncall_owner` and run it again.

> "For on-call, it finds the moment the second source made it disputed."

## 1:50–2:10 · `impact` (`/app/impact`)

Select the `region-a` chip (it should already be selected). Click **Simulate an agent that acted on 15 Oct**.

> "A fact got corrected. What already relied on it? Faultline walks the graph backwards from region-a to every snapshot, replay answer and handoff, and flags those that saw it as current. That's the blast radius of a correction."

## 2:10–2:30 · `handoff` (`/app/handoff`)

Click **Create handoff**, then **Accept as agent-release**.

> "The planner hands the rollout to the release agent. The server copies the on-call dispute onto the handoff. The client can't drop it, so the next agent can't act as if it were settled."

If time allows, click **Try an expired handoff** and point at `409 snapshot_stale`.

## 2:30–2:50 · `test`: proof the graph does the work (`/app/bench`)

Point at **Memory regression tests: 6 passed**, then click **Run ablation**.

> "Memory has regression tests: at this time, this question must give this answer. They run in CI on every push. And the ablation deletes a real FalkorDB edge: remove SUPPORTED_BY and region-b is gone; remove SUPERSEDES and Faultline refuses to choose. Then both edges are restored."

Optionally cut for 3 seconds to the GitHub Actions tab showing green `api`, `web` and `deploy` jobs.

## 2:50–3:00 · Close (back to landing)

> "Faultline: blame, diff, bisect and test what your agents remembered. Live at faultline.mannnan.com, code on GitHub. Built for Graph Hacks Track 02 on FalkorDB."

---

## Submission checklist

- [x] Video uploaded: https://youtu.be/7pAOF6mY3M4. Link pasted into the README's top line and the submission form
- [ ] Repo is public: https://github.com/maannaan/faultline
- [ ] Live URL: https://faultline.mannnan.com
- [ ] Track: **02, Agent Memory and Coordination**
- [ ] AI assistance disclosed (README, last section)
- [ ] Submitted before **23:59 IST, 18 Oct 2026**

## 60-second pitch (for the form)

When an AI agent gives a stale or contradictory answer, developers can't reproduce what it knew or why the answer changed. Faultline is git for agent memory, built on FalkorDB.

Every fact is an assertion linked to its source and observation time. Corrections are SUPERSEDES edges and disagreements are CONFLICTS_WITH edges, so nothing is overwritten. On top of that graph, Faultline provides:
- `checkout`: reconstruct memory at any moment
- `diff`: compare the same question across snapshots and name the edge that changed the answer
- `blame`: trace an answer back to the agent that recorded it
- `bisect`: find the exact event that flipped an answer
- `impact`: find every replay and handoff that relied on a corrected fact
- `handoff`: carry unresolved conflicts to the next agent

Memory regression tests run in CI on every push. Edge ablation shows the graph does the work: delete one relationship and the answer changes.
