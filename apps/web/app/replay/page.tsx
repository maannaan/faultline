import { ApiRequestError, serverGet } from "@/lib/api";
import type { Entity } from "@/lib/types";
import { ReplayLab } from "./replay-lab";

export const dynamic = "force-dynamic";

export default async function ReplayPage() {
  try {
    const entityList = await serverGet<{ entities: Entity[] }>("/v1/entities");
    return <ReplayLab entities={entityList.entities} apiError={null} />;
  } catch (error) {
    const message = error instanceof ApiRequestError ? error.message : "The timeline could not be loaded.";
    return <ReplayLab entities={[]} apiError={message} />;
  }
}
