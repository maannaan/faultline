import { ApiRequestError, serverGet } from "@/lib/api";
import type { Entity, Timeline } from "@/lib/types";
import { TimelineBoard } from "./timeline-board";

export const dynamic = "force-dynamic";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ entity?: string }>;
}) {
  const params = await searchParams;
  try {
    const entityList = await serverGet<{ entities: Entity[] }>("/v1/entities");
    const selected =
      params.entity && entityList.entities.some((entity) => entity.entity_id === params.entity)
        ? params.entity
        : (entityList.entities[0]?.entity_id ?? "");
    let timeline: Timeline | null = null;
    if (selected) {
      timeline = await serverGet<Timeline>(
        `/v1/timeline?entity_id=${encodeURIComponent(selected)}`,
      );
    }
    return (
      <TimelineBoard
        entities={entityList.entities}
        timeline={timeline}
        selectedEntity={selected}
        apiError={null}
      />
    );
  } catch (error) {
    const message = error instanceof ApiRequestError ? error.message : "The timeline could not be loaded.";
    return <TimelineBoard entities={[]} timeline={null} selectedEntity="" apiError={message} />;
  }
}
