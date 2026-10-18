import type { ReactNode } from "react";

/** Map any assertion or claim status onto one of the four status colors. */
export function statusTone(status: string | null | undefined): string {
  switch (status) {
    case "current":
    case "supported":
    case "completed":
      return "current";
    case "superseded":
      return "superseded";
    case "disputed":
    case "stale":
      return "disputed";
    case "unverified":
    case "insufficient":
      return "unverified";
    default:
      return "neutral";
  }
}

export function StatusPill({ status, prefix }: { status: string | null | undefined; prefix?: string }) {
  const tone = statusTone(status);
  return (
    <span className={`pill pill-${tone}`}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {prefix ? <span className="opacity-70">{prefix}</span> : null}
      {status ?? "unknown"}
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {description ? <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}

export function Panel({
  title,
  aside,
  children,
  className = "",
}: {
  title?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title ? (
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
          <h2 className="text-sm font-medium">{title}</h2>
          {aside ? <div className="text-xs text-dim">{aside}</div> : null}
        </div>
      ) : null}
      <div className="panel-pad">{children}</div>
    </section>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line2 bg-white/[0.015] p-6 text-sm leading-6 text-muted">
      {children}
    </div>
  );
}

export function ErrorBanner({ title = "API unavailable", children }: { title?: string; children: ReactNode }) {
  return (
    <div role="alert" className="rounded-xl border border-disputed/30 bg-disputed/[0.06] p-4 text-sm">
      <p className="font-medium text-disputed">{title}</p>
      <div className="mt-1 leading-6 text-muted">{children}</div>
    </div>
  );
}

export function KeyValue({ rows }: { rows: Array<[string, ReactNode]> }) {
  return (
    <dl className="grid gap-2.5 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="grid grid-cols-[110px_1fr] gap-3">
          <dt className="text-dim">{label}</dt>
          <dd className="mono min-w-0 break-all text-[13px] text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    hour12: false,
  }) + " UTC";
}

export function localInputValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
