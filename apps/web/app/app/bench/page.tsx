import { ApiRequestError, serverGet } from "@/lib/api";
import { BenchView } from "./bench-view";

export const dynamic = "force-dynamic";

export default async function BenchPage() {
  try {
    await serverGet<{ status: string }>("/health");
    return <BenchView apiError={null} />;
  } catch (error) {
    const message =
      error instanceof ApiRequestError ? error.message : "The Faultline API is not reachable.";
    return <BenchView apiError={message} />;
  }
}
