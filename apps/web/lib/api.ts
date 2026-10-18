import type { ApiError } from "./types";

const apiBase = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
const apiKey = process.env.FAULTLINE_API_KEY ?? "dev-key";

export class ApiRequestError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function serverGet<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      headers: { Authorization: `Bearer ${apiKey}` },
      cache: "no-store",
    });
  } catch {
    throw new ApiRequestError(503, "The Faultline API is not reachable.");
  }
  if (!response.ok) {
    throw new ApiRequestError(response.status, await readError(response));
  }
  return (await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ApiError;
    return body.error?.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}
