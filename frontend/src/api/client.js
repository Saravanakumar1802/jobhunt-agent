/**
 * Fetch wrapper: base URL, JWT header, JSON in/out and one error shape.
 * Backend errors look like {"error": {"code", "message", "details"?}}.
 */

const BASE = import.meta.env.VITE_API_URL ?? ""; // "" → same origin (Vite dev proxy)
const TOKEN_KEY = "jhc.token";

let token = readToken();
let unauthorizedHandler = null;

function readToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // storage blocked (private mode) — keep the session in memory only
  }
}

export function setToken(value) {
  token = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* in-memory token still works */
  }
}

export const getToken = () => token;
export const onUnauthorized = (fn) => (unauthorizedHandler = fn);

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function authHeaders() {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function url(path) {
  return `${BASE}/api${path}`;
}

export async function toApiError(res) {
  let body = {};
  try {
    body = await res.json();
  } catch {
    /* non-JSON error */
  }
  const err = body.error ?? {};
  const message =
    err.code === "validation_error" && err.details?.length
      ? err.details.map((d) => `${d.field || "field"}: ${d.msg}`).join("; ")
      : err.message ?? `Request failed (${res.status})`;
  return new ApiError(res.status, err.code ?? "http_error", message, err.details);
}

export async function api(path, { method = "GET", body, signal } = {}) {
  let res;
  try {
    res = await fetch(url(path), {
      method,
      signal,
      headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...authHeaders() },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError(0, "network", "Can't reach the server. Is the backend running?");
  }
  if (res.status === 401 && token) unauthorizedHandler?.();
  if (!res.ok) throw await toApiError(res);
  return res.status === 204 ? null : res.json();
}

/** Job ids contain ":" and other symbols — always encode them in paths. */
export const enc = (id) => encodeURIComponent(id);
