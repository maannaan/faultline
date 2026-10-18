"use client";

import { TriangleAlert } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { EmptyState, ErrorBanner, KeyValue, PageHeader, Panel, StatusPill, formatTime, localInputValue } from "@/components/ui";
import type { SnapshotResult, TaskView } from "@/lib/types";

type Props = {
  apiError: string | null;
};

const LATE = "2026-10-16T13:00:00Z";
const PAST = "2026-10-16T00:00:00Z";

export function HandoffInspector({ apiError }: Props) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [staleBlock, setStaleBlock] = useState<string | null>(null);
  const [task, setTask] = useState<TaskView | null>(null);

  async function onCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    setStaleBlock(null);
    try {
      const created = await createTransfer({
        objective: String(data.get("objective") || ""),
        criteria: String(data.get("criteria") || ""),
        question: String(data.get("question") || ""),
        expiresAt: new Date(String(data.get("expires_at") || "")).toISOString(),
        refs: selectedRefs(data),
      });
      setTask(created);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The handoff could not be created.");
    } finally {
      setPending(false);
    }
  }

  async function onAccept() {
    if (!task) return;
    setPending(true);
    setError(null);
    try {
      const accepted = await postJson<TaskView>(`/v1/tasks/${task.task_id}/accept`, {
        agent_id: "agent-release",
        expected_version: task.version,
      });
      setTask(accepted);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Accept failed.");
    } finally {
      setPending(false);
    }
  }

  async function onComplete(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!task) return;
    const result = String(new FormData(event.currentTarget).get("result") || "");
    setPending(true);
    setError(null);
    try {
      const completed = await postJson<TaskView>(`/v1/tasks/${task.task_id}/complete`, {
        expected_version: task.version,
        result,
        evidence_refs: task.handoff?.memory_refs ?? [],
      });
      setTask(completed);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Complete failed.");
    } finally {
      setPending(false);
    }
  }

  async function onExpired() {
    setPending(true);
    setError(null);
    setStaleBlock(null);
    try {
      const created = await createTransfer({
        objective: "Prepare the Atlas rollout checklist",
        criteria: "Use the accepted deploy region\nSurface unresolved memory conflicts before proceeding",
        question: "This expiry is already past.",
        expiresAt: PAST,
        refs: ["assert-region-b", "source-change-002"],
      });
      const accepted = await postJson<TaskView>(`/v1/tasks/${created.task_id}/accept`, {
        agent_id: "agent-release",
        expected_version: created.version,
      });
      try {
        await postJson<TaskView>(`/v1/tasks/${accepted.task_id}/complete`, {
          expected_version: accepted.version,
          result: "Should stay uncompleted",
          evidence_refs: ["assert-region-b"],
        });
        setError("The expired handoff completed, which should not happen.");
        setTask(accepted);
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "Snapshot is stale";
        setStaleBlock(message);
        const current = await getJson<TaskView>(`/v1/tasks/${accepted.task_id}`);
        setTask(current);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The expired handoff could not be created.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="faultline handoff"
        title="Pass the snapshot, keep the dispute"
        description="The planner hands a versioned snapshot to the release agent. The server copies every disputed assertion onto the handoff, so the client cannot drop it."
      />
      {apiError ? <ErrorBanner>{apiError}</ErrorBanner> : null}
      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <Panel title="New handoff">
          <form onSubmit={onCreate} className="space-y-4">
            <Field label="Objective" id="objective">
              <textarea id="objective" name="objective" required rows={2} defaultValue="Prepare the Atlas rollout checklist" className="field" />
            </Field>
            <Field label="Acceptance criteria" id="criteria">
              <textarea
                id="criteria"
                name="criteria"
                required
                rows={3}
                defaultValue={"Use the accepted deploy region\nSurface unresolved memory conflicts before proceeding"}
                className="field"
              />
            </Field>
            <Field label="Open question" id="question">
              <input id="question" name="question" required defaultValue="Who is on call for the rollout?" className="field" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Recipient" id="recipient">
                <input id="recipient" readOnly value="agent-release" className="field mono !text-xs" />
              </Field>
              <Field label="Expiry" id="expires-at">
                <input
                  id="expires-at"
                  name="expires_at"
                  type="datetime-local"
                  required
                  defaultValue={localInputValue(new Date("2026-10-20T00:00:00Z"))}
                  className="field !px-2 !text-xs"
                />
              </Field>
            </div>
            <fieldset className="space-y-2 rounded-lg border border-line bg-black/30 p-3 text-sm">
              <legend className="label px-1">Memory refs</legend>
              <label className="mono flex items-center gap-2 text-xs" htmlFor="ref-region">
                <input id="ref-region" name="ref" type="checkbox" value="assert-region-b" defaultChecked className="accent-[#f59e0b]" />
                assert-region-b
              </label>
              <label className="mono flex items-center gap-2 text-xs" htmlFor="ref-source">
                <input id="ref-source" name="ref" type="checkbox" value="source-change-002" defaultChecked className="accent-[#f59e0b]" />
                source-change-002
              </label>
            </fieldset>
            <button type="submit" disabled={pending || Boolean(apiError)} className="btn btn-primary w-full">
              {pending ? "Writing…" : "Create handoff"}
            </button>
            <button type="button" onClick={onExpired} disabled={pending || Boolean(apiError)} className="btn btn-fault w-full">
              Try an expired handoff
            </button>
            {error ? <p className="text-xs leading-5 text-disputed">{error}</p> : null}
          </form>
        </Panel>
        <section className="min-w-0 space-y-4">
          {!task && !apiError ? (
            <EmptyState>No handoff yet. Create one from the late Project Atlas snapshot at {formatTime(LATE)}.</EmptyState>
          ) : null}
          {task ? <TaskCard task={task} pending={pending} onAccept={onAccept} onComplete={onComplete} /> : null}
          {staleBlock ? (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
              <ErrorBanner title="409 snapshot_stale">{staleBlock} The task stays uncompleted and no result is stored.</ErrorBanner>
            </motion.div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

const STEPS = [
  { key: "queued", label: "Created", agent: "agent-planner" },
  { key: "handed_off", label: "Handed off", agent: "agent-planner" },
  { key: "claimed", label: "Claimed", agent: "agent-release" },
  { key: "completed", label: "Completed", agent: "agent-release" },
] as const;

function TaskCard({
  task,
  pending,
  onAccept,
  onComplete,
}: {
  task: TaskView;
  pending: boolean;
  onAccept: () => void;
  onComplete: (event: React.FormEvent<HTMLFormElement>) => void;
}) {
  const handoff = task.handoff;
  const reached = Math.max(0, STEPS.findIndex((step) => step.key === task.status));
  return (
    <motion.div layout className="panel overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3 sm:px-5">
        <h2 className="text-sm font-medium">{task.objective}</h2>
        <span className="pill pill-neutral mono">v{task.version}</span>
        {handoff?.stale ? <StatusPill status="stale" /> : null}
        <span className="mono ml-auto text-[11px] text-dim">owner {task.owner_agent_id}</span>
      </div>
      <ol className="grid grid-cols-4 border-b border-line">
        {STEPS.map((step, index) => {
          const done = index <= reached;
          return (
            <li key={step.key} className="relative px-3 py-3 sm:px-4">
              <motion.div
                className="absolute inset-x-0 top-0 h-0.5 bg-fault"
                initial={false}
                animate={{ scaleX: done ? 1 : 0 }}
                style={{ originX: 0 }}
                transition={{ duration: 0.5, delay: index * 0.08 }}
              />
              <p className={`text-xs font-medium ${done ? "text-ink" : "text-dim"}`}>{step.label}</p>
              <p className="mono mt-0.5 truncate text-[10px] text-dim">{step.agent}</p>
            </li>
          );
        })}
      </ol>
      <div className="panel-pad space-y-5">
        {handoff && handoff.unresolved_conflicts.length > 0 ? (
          <div className="rounded-lg border border-disputed/30 bg-disputed/[0.05] p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-disputed">
              <TriangleAlert className="size-4" /> Unresolved conflict carried forward
            </div>
            <p className="mt-1 text-xs leading-5 text-muted">Copied by the server from the snapshot. The receiving agent must see both before acting.</p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {handoff.unresolved_conflicts.map((item) => (
                <li key={item.assertion_id} className="rounded-md border border-line bg-black/30 p-2.5">
                  <p className="text-sm font-medium">{item.value}</p>
                  <p className="mono mt-0.5 text-[10px] text-dim">
                    {item.assertion_id} · {item.source_id}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        ) : handoff ? (
          <p className="text-sm text-dim">No unresolved conflicts in this snapshot.</p>
        ) : null}
        <KeyValue
          rows={[
            ["Snapshot", handoff?.snapshot_id ?? "—"],
            ["Memory refs", handoff?.memory_refs.join(", ") || "—"],
            ["Criteria", task.acceptance_criteria.join("; ")],
            ["Open question", handoff?.open_questions.join("; ") || "—"],
            ["Expires", formatTime(handoff?.expires_at)],
          ]}
        />
        {handoff?.stale_reason ? <p className="text-sm text-disputed">{handoff.stale_reason}</p> : null}
        {handoff?.result ? (
          <p className="rounded-lg border border-ok/30 bg-ok/[0.05] p-3 text-sm">
            <span className="text-ok">Result · </span>
            {handoff.result}
          </p>
        ) : null}
        {task.status === "handed_off" ? (
          <button type="button" onClick={onAccept} disabled={pending} className="btn btn-primary">
            Accept as agent-release
          </button>
        ) : null}
        {task.status === "claimed" ? (
          <form onSubmit={onComplete} className="flex flex-col gap-2 sm:flex-row">
            <input
              name="result"
              required
              defaultValue="Checklist uses region-b and leaves the on-call dispute open"
              className="field !mt-0 flex-1"
            />
            <button type="submit" disabled={pending} className="btn btn-primary">
              Complete
            </button>
          </form>
        ) : null}
      </div>
    </motion.div>
  );
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="label" htmlFor={id}>
        {label}
      </label>
      {children}
    </div>
  );
}

function selectedRefs(data: FormData): string[] {
  const refs = data.getAll("ref").map(String).filter(Boolean);
  if (refs.length === 0) {
    throw new Error("Choose at least one memory ref.");
  }
  return refs;
}

async function createTransfer(input: {
  objective: string;
  criteria: string;
  question: string;
  expiresAt: string;
  refs: string[];
}): Promise<TaskView> {
  const stamp = `${Date.now()}`;
  const snapshot = await postJson<SnapshotResult>("/v1/snapshots", {
    as_of_time: LATE,
    time_mode: "known",
    entity_ids: ["project-atlas"],
    idempotency_key: `ui-handoff-snap:project-atlas:${LATE}`,
  });
  const created = await postJson<{ task_id: string; version: number }>("/v1/tasks", {
    objective: input.objective,
    owner_agent_id: "agent-planner",
    acceptance_criteria: input.criteria.split("\n").map((line) => line.trim()).filter(Boolean),
    idempotency_key: `ui-task:${stamp}`,
  });
  return postJson<TaskView>(`/v1/tasks/${created.task_id}/handoff`, {
    to_agent_id: "agent-release",
    snapshot_id: snapshot.snapshot_id,
    memory_refs: input.refs,
    expected_version: created.version,
    idempotency_key: `ui-handoff:${stamp}`,
    open_questions: [input.question],
    expires_at: input.expiresAt,
  });
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api/faultline${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJson<T>(response);
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`/api/faultline${path}`);
  return readJson<T>(response);
}

async function readJson<T>(response: Response): Promise<T> {
  const body = (await response.json()) as T & { error?: { message?: string; code?: string } };
  if (!response.ok) {
    throw new Error(body.error?.message || "The Faultline API is not reachable.");
  }
  return body;
}
