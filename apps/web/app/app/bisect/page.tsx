import { ApiRequestError, serverGet } from "@/lib/api";
import type { Entity } from "@/lib/types";
import { BisectView } from "./bisect-view";

export const dynamic = "force-dynamic";

export default async function BisectPage() {
  try {
    const entityList = await serverGet<{ entities: Entity[] }>("/v1/entities");
    return <BisectView entities={entityList.entities} apiError={null} />;
  } catch (error) {
    const message = error instanceof ApiRequestError ? error.message : "The Faultline API is not reachable.";
    return <BisectView entities={[]} apiError={message} />;
  }
}
