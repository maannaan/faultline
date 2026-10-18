import { ApiRequestError, serverGet } from "@/lib/api";
import type { Entity, Timeline } from "@/lib/types";
import { ImpactView } from "./impact-view";

export const dynamic = "force-dynamic";

export default async function ImpactPage() {
  try {
    const entityList = await serverGet<{ entities: Entity[] }>("/v1/entities");
    const entityId = entityList.entities[0]?.entity_id;
    const timeline = entityId
      ? await serverGet<Timeline>(`/v1/timeline?entity_id=${encodeURIComponent(entityId)}`)
      : null;
    return <ImpactView items={timeline?.items ?? []} apiError={null} />;
  } catch (error) {
    const message = error instanceof ApiRequestError ? error.message : "The Faultline API is not reachable.";
    return <ImpactView items={[]} apiError={message} />;
  }
}
