// frontend/lib/aiDirect.ts — call AI providers straight from the device.
//
// Normally the model call happens in the backend, where the API key is sealed
// with SETTINGS_ENCRYPTION_KEY and the tool/memory/knowledge/audit layers wrap
// it. That path needs the desktop to be reachable. This module is the opt-in
// alternative for the phone: the key lives in Android Keystore on the device
// and the provider is called directly from the WebView.
//
// The trade-off is real and not recoverable here — a direct call is plain text
// in, plain text out. No tool calling, no approval proposals, no section
// memory, no AI Knowledge retrieval, no debate or reasoning council, no audit
// trail, and no quality gate. Anything needing those has to go through the
// backend. Callers surface that difference rather than hiding it.
//
// Security: a key stored on the device can be extracted by anyone who controls
// the device. Scope the keys used here to the minimum the phone needs, and
// prefer the backend path whenever it is reachable.
import { credentialStorage } from "@/lib/credentialStorage";

// Anthropic and Gemini each have their own request shape; every other provider
// AllHaven supports speaks the OpenAI /chat/completions shape and differs only
// by base URL. Defaults mirror backend/app/services/ai_providers/*.
type Wire = "openai" | "anthropic" | "gemini";

type Spec = { wire: Wire; base: string; model: string };

const PROVIDERS: Record<string, Spec> = {
  openai: { wire: "openai", base: "https://api.openai.com/v1", model: "gpt-4.1-mini" },
  grok: { wire: "openai", base: "https://api.x.ai/v1", model: "grok-2-latest" },
  deepseek: { wire: "openai", base: "https://api.deepseek.com/v1", model: "deepseek-chat" },
  openrouter: { wire: "openai", base: "https://openrouter.ai/api/v1", model: "openai/gpt-4.1-mini" },
  qwen: { wire: "openai", base: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" },
  blackbox: { wire: "openai", base: "https://api.blackbox.ai/v1", model: "blackbox-default" },
  anthropic: { wire: "anthropic", base: "https://api.anthropic.com/v1", model: "claude-sonnet-4-5" },
  gemini: { wire: "gemini", base: "https://generativelanguage.googleapis.com/v1beta", model: "gemini-1.5-flash" },
};

// Ollama is deliberately absent: it runs on the desktop, so a phone calling it
// directly would need the bridge that makes the backend path work anyway.
export const directProviderIds = Object.keys(PROVIDERS);
export const supportsDirect = (providerId: string) => providerId in PROVIDERS;

// --- on-device key storage -------------------------------------------------
// credentialStorage is Android Keystore-backed on native and Preferences in the
// browser; see lib/credentialStorage.ts.
const keyName = (providerId: string) => `ai_key_${providerId}`;

export const getProviderKey = (providerId: string) => credentialStorage.getItem(keyName(providerId));
export const setProviderKey = (providerId: string, key: string) =>
  credentialStorage.setItem(keyName(providerId), key.trim());
export const clearProviderKey = (providerId: string) => credentialStorage.removeItem(keyName(providerId));

/** Provider ids that have a key on this device, in `directProviderIds` order. */
export async function configuredProviders(): Promise<string[]> {
  const found = await Promise.all(
    directProviderIds.map(async (id) => ((await getProviderKey(id)) ? id : null)),
  );
  return found.filter((id): id is string => id !== null);
}

export class DirectChatError extends Error {
  constructor(message: string, readonly providerId: string) {
    super(message);
    this.name = "DirectChatError";
  }
}

export type DirectMessage = { role: "system" | "user" | "assistant"; content: string };

// A data URL splits into the media type and the bare base64 payload; Anthropic
// and Gemini both want them as separate fields.
function splitDataUrl(dataUrl: string): { media: string; b64: string } | null {
  const m = /^data:([^;]+);base64,(.+)$/.exec(dataUrl);
  return m ? { media: m[1], b64: m[2] } : null;
}

async function readBody(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  try {
    const j = JSON.parse(text);
    return j?.error?.message || j?.error?.type || j?.message || text.slice(0, 300);
  } catch {
    return text.slice(0, 300);
  }
}

async function callOpenAi(spec: Spec, key: string, model: string, messages: DirectMessage[], images: string[]) {
  // Images ride on the last user turn as image_url parts.
  const body = {
    model,
    messages: messages.map((m, i) =>
      i === messages.length - 1 && images.length
        ? {
            role: m.role,
            content: [
              { type: "text", text: m.content },
              ...images.map((url) => ({ type: "image_url", image_url: { url } })),
            ],
          }
        : m,
    ),
  };
  const res = await fetch(`${spec.base}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readBody(res));
  const data = await res.json();
  return String(data?.choices?.[0]?.message?.content ?? "").trim();
}

async function callAnthropic(spec: Spec, key: string, model: string, messages: DirectMessage[], images: string[]) {
  const system = messages.find((m) => m.role === "system")?.content;
  const convo = messages.filter((m) => m.role !== "system");
  const body: Record<string, unknown> = {
    model,
    max_tokens: 4096,
    messages: convo.map((m, i) => {
      if (i !== convo.length - 1 || !images.length) return { role: m.role, content: m.content };
      const parts: unknown[] = [];
      for (const url of images) {
        const img = splitDataUrl(url);
        if (img) parts.push({ type: "image", source: { type: "base64", media_type: img.media, data: img.b64 } });
      }
      parts.push({ type: "text", text: m.content });
      return { role: m.role, content: parts };
    }),
  };
  if (system) body.system = system;
  const res = await fetch(`${spec.base}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
      // Required for browser-origin calls. The Capacitor WebView is an origin
      // (https://localhost), so without this the request is rejected before it
      // reaches the model. The name is a warning, not a formality: it opts into
      // shipping the key to a client anyone can inspect.
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readBody(res));
  const data = await res.json();
  const text = (data?.content ?? [])
    .filter((b: { type?: string }) => b?.type === "text")
    .map((b: { text?: string }) => b.text ?? "")
    .join("");
  return String(text).trim();
}

async function callGemini(spec: Spec, key: string, model: string, messages: DirectMessage[], images: string[]) {
  const system = messages.find((m) => m.role === "system")?.content;
  const convo = messages.filter((m) => m.role !== "system");
  const contents = convo.map((m, i) => {
    const parts: unknown[] = [{ text: m.content }];
    if (i === convo.length - 1) {
      for (const url of images) {
        const img = splitDataUrl(url);
        if (img) parts.push({ inline_data: { mime_type: img.media, data: img.b64 } });
      }
    }
    return { role: m.role === "assistant" ? "model" : "user", parts };
  });
  const body: Record<string, unknown> = { contents };
  if (system) body.system_instruction = { parts: [{ text: system }] };
  const res = await fetch(`${spec.base}/models/${encodeURIComponent(model)}:generateContent`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-goog-api-key": key },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readBody(res));
  const data = await res.json();
  const text = (data?.candidates?.[0]?.content?.parts ?? [])
    .map((p: { text?: string }) => p?.text ?? "")
    .join("");
  return String(text).trim();
}

/**
 * Send one turn to a provider from this device and return its reply text.
 *
 * Throws DirectChatError when no key is stored, the provider is unsupported, or
 * the provider rejects the call — callers render that verbatim rather than
 * substituting a generic failure, so the reason stays honest.
 */
export async function directChat(
  providerId: string,
  messages: DirectMessage[],
  opts: { model?: string; images?: string[] } = {},
): Promise<string> {
  const spec = PROVIDERS[providerId];
  if (!spec) throw new DirectChatError(`${providerId} can't be called directly from this device.`, providerId);

  const key = await getProviderKey(providerId);
  if (!key) {
    throw new DirectChatError(
      `No API key saved on this device for ${providerId}. Add one in Settings → On-device AI keys.`,
      providerId,
    );
  }

  const model = opts.model?.trim() || spec.model;
  const images = opts.images ?? [];
  try {
    const call = spec.wire === "anthropic" ? callAnthropic : spec.wire === "gemini" ? callGemini : callOpenAi;
    const text = await call(spec, key, model, messages, images);
    if (!text) throw new Error("The provider returned an empty response.");
    return text;
  } catch (err) {
    throw new DirectChatError(err instanceof Error ? err.message : `${providerId} call failed.`, providerId);
  }
}
