export type Entity = {
  entity_id: string;
  entity_type: string;
  canonical_name: string;
};

export type TimelineItem = {
  assertion_id: string;
  predicate: string;
  value: string;
  status: "current" | "superseded" | "disputed" | "unverified" | string;
  observed_at: string;
  valid_from: string | null;
  valid_to: string | null;
  confidence: number;
  source_id: string | null;
  event_id: string | null;
  supersedes_ids: string[];
  conflicts_with_ids: string[];
  resolution: string;
  resolution_reason: string;
  policy_version: string;
};

export type Timeline = {
  entity_id: string;
  policy_version: string;
  items: TimelineItem[];
};

export type SnapshotMember = {
  assertion_id: string;
  predicate: string;
  value: string;
  status: string;
  observed_at: string;
  valid_from: string | null;
  valid_to: string | null;
  confidence: number;
  source_id: string | null;
  event_id: string | null;
  supersedes_ids: string[];
  conflicts_with_ids: string[];
  reason: string;
};

export type SnapshotResult = {
  snapshot_id: string;
  as_of_time: string;
  time_mode: "known" | "valid" | string;
  policy_version: string;
  included: SnapshotMember[];
  validity_unknown_ids: string[];
};

export type ReplayClaim = {
  claim_id: string;
  predicate: string;
  value: string | null;
  status: string;
  evidence_ids: string[];
  wording: string;
};

export type ReplayResult = {
  replay_id: string;
  snapshot_id: string;
  claims: ReplayClaim[];
  model_version: string;
  prompt_version: string;
  citation_rejected: boolean;
};

export type ReplayDiff = {
  baseline_replay_id: string;
  candidate_replay_id: string;
  added: string[];
  removed: string[];
  unchanged: string[];
  status_changed: Array<{ assertion_id: string; from_status: string; to_status: string }>;
  added_source_ids: string[];
  removed_source_ids: string[];
  answer_change: string;
  explanation: string;
};

export type NoteResult = {
  source_id: string;
  event_id: string;
  extraction_status: "completed" | "failed";
  extraction_error: string | null;
  warnings: string[];
  assertions: Array<{
    assertion_id: string;
    status: string;
    resolution: string;
  }>;
};

export type ApiError = {
  error: {
    code: string;
    message: string;
    correlation_id: string;
  };
};

export type ConflictItem = {
  assertion_id: string;
  predicate: string;
  value: string;
  source_id: string | null;
};

export type HandoffView = {
  handoff_id: string;
  snapshot_id: string;
  memory_refs: string[];
  unresolved_conflicts: ConflictItem[];
  stale: boolean;
  stale_reason: string | null;
  from_agent_id: string;
  to_agent_id: string;
  expires_at: string;
  open_questions: string[];
  result: string | null;
  evidence_refs: string[];
};

export type IncludedFact = {
  assertion_id: string;
  status: string;
  value: string;
};

export type BenchClaim = {
  status: string;
  value: string | null;
  evidence_ids: string[];
  included: IncludedFact[];
};

export type AblationReport = {
  intact: BenchClaim;
  support_deleted: BenchClaim;
  supersedes_deleted: BenchClaim;
  restored: boolean;
};

export type TaskView = {
  task_id: string;
  objective: string;
  status: string;
  version: number;
  owner_agent_id: string;
  acceptance_criteria: string[];
  handoff: HandoffView | null;
};

export type GraphNodeKind = "entity" | "assertion" | "source" | "event" | "session" | "agent";

export type GraphNode = {
  id: string;
  kind: GraphNodeKind;
  label: string;
  sublabel: string;
  status: string | null;
  status_now: string | null;
  observed_at: string | null;
  excluded: boolean;
  visible: boolean;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  visible: boolean;
};

export type GraphView = {
  entity_id: string;
  as_of: string;
  time_mode: string;
  moments: string[];
  validity_unknown_ids: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type EvidencePath = {
  assertion_id: string;
  source_id: string | null;
  event_id: string | null;
  session_id: string | null;
  entity_id: string;
  status: string;
  supersedes_ids: string[];
  conflicts_with_ids: string[];
};

export type BisectProbe = {
  as_of: string;
  status: string;
  value: string | null;
  evidence_ids: string[];
  verdict: "good" | "bad";
};

export type BisectResult = {
  entity_id: string;
  predicate: string;
  good: BisectProbe;
  bad: BisectProbe;
  flipped: boolean;
  candidates: number;
  probes: BisectProbe[];
  first_bad_as_of: string | null;
  culprit_assertion_ids: string[];
  culprit_source_ids: string[];
  culprit_event_ids: string[];
  explanation: string;
};

export type ImpactReport = {
  assertion: {
    assertion_id: string;
    predicate: string;
    value: string;
    status_now: string;
    superseded_by: string[];
    conflicts_with: string[];
  };
  snapshots: Array<{
    snapshot_id: string;
    as_of: string;
    status_then: string;
    outdated: boolean;
    replay_count: number;
    handoff_count: number;
  }>;
  replays: Array<{
    replay_id: string;
    question: string;
    snapshot_id: string;
    as_of: string;
    claim_status: string;
    claim_value: string | null;
    status_then: string;
    outdated: boolean;
  }>;
  handoffs: Array<{
    handoff_id: string;
    task_id: string;
    objective: string;
    task_status: string;
    snapshot_id: string;
    as_of: string;
    status_then: string;
    referenced: boolean;
    carried_as_conflict: boolean;
    outdated: boolean;
  }>;
  outdated_count: number;
  summary: string;
};
