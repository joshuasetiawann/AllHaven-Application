import { BEARER_MODE } from "@/lib/mobileAuth";

export interface NativeJsonResponse<T = unknown> {
  status: number;
  data: T | null;
  headers: Record<string, string>;
}

function parseJsonish<T>(value: unknown): T | null {
  if (value == null) return null;
  if (typeof value === "string") {
    try {
      return JSON.parse(value) as T;
    } catch {
      return null;
    }
  }
  return value as T;
}

function bodyToNativeData(body: BodyInit | null | undefined): unknown {
  if (body == null) return undefined;
  if (typeof body !== "string") return body;
  try {
    return JSON.parse(body);
  } catch {
    return body;
  }
}

export async function nativeJsonRequest<T>(
  url: string,
  init: RequestInit = {},
  timeoutMs = 3500,
): Promise<NativeJsonResponse<T> | null> {
  if (!BEARER_MODE || typeof window === "undefined") return null;

  const { Capacitor, CapacitorHttp } = await import("@capacitor/core");
  if (!Capacitor.isNativePlatform()) return null;

  const response = await CapacitorHttp.request({
    url,
    method: (init.method || "GET").toUpperCase(),
    headers: init.headers as Record<string, string> | undefined,
    data: bodyToNativeData(init.body),
    responseType: "json",
    connectTimeout: timeoutMs,
    readTimeout: timeoutMs,
  });

  return {
    status: response.status,
    data: parseJsonish<T>(response.data),
    headers: response.headers || {},
  };
}
