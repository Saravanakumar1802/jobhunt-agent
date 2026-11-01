/**
 * POST /search returns Server-Sent Events. EventSource only supports GET, so we
 * read the response body as a stream and parse SSE frames ourselves.
 *
 * Frame format:  event: <name>\n data: <json>\n\n
 */
import { authHeaders, toApiError, url, ApiError } from "./client";

/** Incremental parser: feed text chunks, get complete events back. Frames may split anywhere. */
export function createSSEParser() {
  let buffer = "";
  return function feed(chunk) {
    buffer += chunk.replace(/\r\n/g, "\n");
    const events = [];
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let event = "message";
      const data = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (!data.length) continue;
      try {
        events.push({ event, data: JSON.parse(data.join("\n")) });
      } catch {
        /* ignore malformed frame */
      }
    }
    return events;
  };
}

export async function streamSearch(body, { onEvent, signal }) {
  let res;
  try {
    res = await fetch(url("/search"), {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...authHeaders() },
      body: JSON.stringify(body),
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError(0, "network", "Can't reach the server. Is the backend running?");
  }
  if (!res.ok) throw await toApiError(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const feed = createSSEParser();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const evt of feed(decoder.decode(value, { stream: true }))) onEvent(evt);
  }
}
