import type { Message } from "./types";

const BASE = "/api";

export async function fetchModels(): Promise<string[]> {
  const res = await fetch(`${BASE}/models`);
  if (!res.ok) throw new Error(`Failed to load models (${res.status})`);
  const data = await res.json();
  return data.models ?? [];
}

/**
 * POST /chat and stream the plain-text response.
 * Calls `onChunk` for every decoded piece as it arrives.
 */
export async function streamChat(
  model: string,
  messages: Message[],
  onChunk: (text: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages }),
    signal,
  });

  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Chat request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
}
