"use client";

import { useState } from "react";
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
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 lg:grid-cols-[320px_1fr] lg:px-6">
      <form onSubmit={onCreate} className="space-y-4 rounded-xl border border-[var(--line)] bg-[var(--card)] p-4">
        <header>
          <p className="mono text-xs tracking-[0.16em] text-[var(--fault)]">HANDOFF</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Pass the snapshot, keep the dispute</h1>
        </header>
        {apiError ? <p className="text-sm text-[var(--fault)]">{apiError}</p> : null}
        <Field label="Objective" id="objective">
          <textarea
            id="objective"
            name="objective"
            required
            rows={2}
            defaultValue="Prepare the Atlas rollout checklist"
            className="w-full rounded-lg border border-[var(--line)] bg-white p-2 text-sm"
          />
        </Field>
        <Field label="Acceptance criteria" id="criteria">
          <textarea
            id="criteria"
            name="criteria"
            required
            rows={3}
            defaultValue={"Use the accepted deploy region\nSurface unresolved memory conflicts before proceeding"}
            className="w-full rounded-lg border border-[var(--line)] bg-white p-2 text-sm"
          />
        </Field>
        <Field label="Open question" id="question">
          <input
            id="question"
            name="question"
            required
            defaultValue="Who is on call for the rollout?"
            className="w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
          />
        </Field>
        <Field label="Recipient" id="recipient">
          <input
            id="recipient"
            readOnly
            value="agent-release"
            className="mono w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
          />
        </Field>
        <Field label="Expiry" id="expires-at">
          <input
            id="expires-at"
            name="expires_at"
            type="datetime-local"
            required
            defaultValue={localInputValue(new Date("2026-10-20T00:00:00Z"))}
            className="w-full rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
          />
        </Field>
        <fieldset className="space-y-2 text-sm">
          <legend className="text-xs text-[var(--muted)]">Memory refs</legend>
          <label className="flex gap-2" htmlFor="ref-region">
            <input id="ref-region" name="ref" type="checkbox" value="assert-region-b" defaultChecked />
            assert-region-b
          </label>
          <label className="flex gap-2" htmlFor="ref-source">
            <input id="ref-source" name="ref" type="checkbox" value="source-change-002" defaultChecked />
            source-change-002
          </label>
        </fieldset>
        <button
          type="submit"
          disabled={pending || Boolean(apiError)}
          className="w-full rounded-lg bg-[var(--ink)] px-3 py-2 text-sm font-medium text-[var(--paper)] disabled:opacity-60"
        >
          {pending ? "Writing…" : "Create handoff"}
        </button>
        <button
          type="button"
          onClick={onExpired}
          disabled={pending || Boolean(apiError)}
          className="w-full rounded-lg border border-[var(--fault)] px-3 py-2 text-sm font-medium text-[var(--fault)] disabled:opacity-60"
        >
          Try an expired handoff
        </button>
        {error ? <p className="text-xs leading-5 text-[var(--fault)]">{error}</p> : null}
      </form>
      <section className="space-y-4">
        {!task && !apiError ? (
          <p className="rounded-xl border border-dashed border-[var(--line)] bg-[var(--card)] p-6 text-sm text-[var(--muted)]">
            No handoff yet. Create one from the late Project Atlas snapshot at {LATE}.
          </p>
        ) : null}
        {task ? <TaskCard task={task} pending={pending} onAccept={onAccept} onComplete={onComplete} /> : null}
        {staleBlock ? (
          <p className="rounded-xl border border-[var(--fault)] bg-[var(--card)] p-4 text-sm text-[var(--fault)]">
            {staleBlock} The task stays uncompleted.
          </p>
        ) : null}
      </section>
    </div>
  );
}

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
  return (
    <div className="space-y-4 rounded-xl border border-[var(--line)] bg-[var(--card)] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold">{task.objective}</h2>
        <span className="mono rounded-full bg-[#efeae4] px-2 py-1 text-xs">{task.status}</span>
        {handoff?.stale ? (
          <span className="rounded-full px-2 py-1 text-xs font-medium status-disputed">stale</span>
        ) : null}
      </div>
      <dl className="grid gap-2 text-sm">
        <Row label="Owner" value={task.owner_agent_id} />
        <Row label="Version" value={String(task.version)} />
        <Row label="Snapshot" value={handoff?.snapshot_id ?? "—"} />
        <Row label="Memory refs" value={handoff?.memory_refs.join(", ") ?? "—"} />
        <Row label="Criteria" value={task.acceptance_criteria.join("; ")} />
      </dl>
      <div>
        <h3 className="text-xs text-[var(--muted)]">Unresolved conflicts</h3>
        {handoff && handoff.unresolved_conflicts.length > 0 ? (
          <ul className="mt-2 space-y-2">
            {handoff.unresolved_conflicts.map((item) => (
              <li key={item.assertion_id} className="rounded-lg border border-[var(--line)] p-2 text-sm">
                <span className="rounded-full px-2 py-1 text-xs font-medium status-disputed">{item.value}</span>
                <p className="mono mt-2 text-xs">
                  {item.assertion_id} · {item.predicate}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-[var(--muted)]">None copied.</p>
        )}
      </div>
      {handoff?.stale_reason ? <p className="text-sm text-[var(--fault)]">{handoff.stale_reason}</p> : null}
      {handoff?.result ? <p className="text-sm">Result: {handoff.result}</p> : null}
      {task.status === "handed_off" ? (
        <button
          type="button"
          onClick={onAccept}
          disabled={pending}
          className="rounded-lg bg-[var(--ink)] px-3 py-2 text-sm font-medium text-[var(--paper)] disabled:opacity-60"
        >
          Accept as agent-release
        </button>
      ) : null}
      {task.status === "claimed" ? (
        <form onSubmit={onComplete} className="flex gap-2">
          <input
            name="result"
            required
            defaultValue="Checklist uses region-b and leaves the on-call dispute open"
            className="flex-1 rounded-lg border border-[var(--line)] bg-white px-2 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={pending}
            className="rounded-lg bg-[var(--ink)] px-3 py-2 text-sm font-medium text-[var(--paper)] disabled:opacity-60"
          >
            Complete
          </button>
        </form>
      ) : null}
    </div>
  );
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-[var(--muted)]" htmlFor={id}>
        {label}
      </label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-2">
      <dt className="text-[var(--muted)]">{label}</dt>
      <dd className="mono break-all">{value}</dd>
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

function localInputValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
