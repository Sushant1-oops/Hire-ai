import type { AuthTokens } from "./types";

export const API_BASE_URL =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "http://localhost:8000";

const ACCESS_KEY = "hireai.access_token";
const REFRESH_KEY = "hireai.refresh_token";

export const tokenStore = {
  get access() {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  set(tokens: AuthTokens) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACCESS_KEY, tokens.access_token);
    if (tokens.refresh_token) window.localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  },
  clear() {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}




interface Envelope<T> {
  error?: boolean;
  message?: string;
  data?: T;
  detail?: string | { msg?: string }[];
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const body = payload as Envelope<unknown>;
  if (typeof body.message === "string" && body.message) return body.message;
  if (typeof body.detail === "string" && body.detail) return body.detail;
  if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg as string;
  return fallback;
}

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh_token = tokenStore.refresh;
  if (!refresh_token) return null;
  if (!refreshing) {
    refreshing = fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    })
      .then(async (res) => {
        if (!res.ok) return null;
        const envelope = (await res.json()) as Envelope<AuthTokens>;
        const data = envelope.data;
        if (!data?.access_token) return null;
        tokenStore.set(data);
        return data.access_token;
      })
      .catch(() => null)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
  responseType?: "json" | "blob";
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const send = async (token: string | null) => {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    let body: BodyInit | undefined;
    if (options.formData) {
      body = options.formData;
    } else if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
    const init: RequestInit = {
      method: options.method ?? (body ? "POST" : "GET"),
      headers,
    };
    if (body !== undefined) init.body = body;
    if (options.signal) init.signal = options.signal;
    return fetch(`${API_BASE_URL}${path}`, init);
  };

  let response: Response;
  try {
    response = await send(tokenStore.access);
  } catch {
    throw new ApiError(`Cannot reach the API at ${API_BASE_URL}`, 0);
  }

  if (response.status === 401 && path !== "/api/auth/login" && path !== "/api/auth/register") {
    const newToken = await refreshAccessToken();
    if (newToken) {
      response = await send(newToken);
    } else {
      tokenStore.clear();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      throw new ApiError("Your session expired. Please sign in again.", 401);
    }
  }

  const status = response.status;

  if (!response.ok) {
    const text = await response.text();
    let parsed: unknown = undefined;
    if (text) {
      try {
        parsed = JSON.parse(text);
      } catch {
        // ignore
      }
    }
    throw new ApiError(extractErrorMessage(parsed, `Request failed (${status})`), status);
  }

  if (status === 204) return undefined as T;

  if (options.responseType === "blob") {
    return (await response.blob()) as T;
  }

  const text = await response.text();
  let parsed: unknown = undefined;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      // ignore
    }
  }

  if (parsed === undefined) return undefined as T;

  const envelope = parsed as Envelope<T>;
  if (envelope && typeof envelope === "object" && "data" in envelope && "error" in envelope) {
    return envelope.data as T;
  }
  return parsed as T;
}
