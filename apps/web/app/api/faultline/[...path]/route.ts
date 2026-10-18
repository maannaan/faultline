import { NextRequest, NextResponse } from "next/server";

const apiBase = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
const apiKey = process.env.FAULTLINE_API_KEY ?? "dev-key";

async function proxy(request: NextRequest, path: string[]) {
  const target = new URL(`${apiBase}/${path.join("/")}`);
  target.search = request.nextUrl.search;
  const headers = new Headers();
  headers.set("Authorization", `Bearer ${apiKey}`);
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }
  const correlation = request.headers.get("x-correlation-id");
  if (correlation) {
    headers.set("X-Correlation-ID", correlation);
  }
  let response: Response;
  try {
    response = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "api_unreachable",
          message: "The Faultline API is not reachable.",
          correlation_id: correlation ?? "",
        },
      },
      { status: 503 },
    );
  }
  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
    },
  });
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxy(request, path);
}
