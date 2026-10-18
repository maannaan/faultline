import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "./ui";

export function ComingSoon({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <div className="grid-bg relative overflow-hidden rounded-xl border border-dashed border-line2 p-10 text-center">
        <p className="pill pill-neutral mx-auto">in progress</p>
        <p className="mx-auto mt-4 max-w-md text-sm leading-6 text-muted">
          This view is being wired to its FalkorDB query. Meanwhile, the Time Machine and Replay Lab run on the same graph.
        </p>
        <Link href="/app/timeline" className="btn btn-ghost mt-6">
          Open the Time Machine <ArrowRight className="size-4" />
        </Link>
      </div>
    </div>
  );
}
