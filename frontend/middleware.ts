import { NextRequest, NextResponse } from "next/server";
import { buildContentSecurityPolicy } from "@/lib/contentSecurityPolicy";

export function middleware(request: NextRequest) {
  // Fast Refresh needs eval in development. Production receives a unique nonce
  // on every document request; Next reads it from the request CSP and applies it
  // to its own bootstrap and streamed scripts.
  if (process.env.NODE_ENV !== "production") return NextResponse.next();

  const nonce = crypto.randomUUID().replaceAll("-", "");
  const policy = buildContentSecurityPolicy({
    nonce,
    deploymentProfile: process.env.NEXT_PUBLIC_DEPLOYMENT_PROFILE || "private",
  });
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", policy);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
