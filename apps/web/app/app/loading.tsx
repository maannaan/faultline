export default function Loading() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading">
      <div className="h-3 w-24 animate-pulse rounded bg-white/[0.06]" />
      <div className="h-8 w-72 animate-pulse rounded bg-white/[0.06]" />
      <div className="h-[420px] animate-pulse rounded-xl border border-line bg-white/[0.02]" />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="h-40 animate-pulse rounded-xl border border-line bg-white/[0.02]" />
        <div className="h-40 animate-pulse rounded-xl border border-line bg-white/[0.02]" />
      </div>
    </div>
  );
}
