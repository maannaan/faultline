import { ApiRequestError, serverGet } from "@/lib/api";
import { HandoffInspector } from "./handoff-inspector";

export const dynamic = "force-dynamic";

export default async function HandoffPage() {
  try {
    await serverGet<{ status: string }>("/health");
    return <HandoffInspector apiError={null} />;
  } catch (error) {
    const message =
      error instanceof ApiRequestError ? error.message : "The Faultline API is not reachable.";
    return <HandoffInspector apiError={message} />;
  }
}
