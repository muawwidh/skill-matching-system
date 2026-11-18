import { sendWithRefresh, singleFlight } from "./authRefresh";
import type { TokenPair } from "../types/auth";
import { clearTokens, getAccessToken, getRefreshToken, saveTokens } from "../features/auth/tokenStorage";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type RequestOptions = RequestInit & {
  accessToken?: string | null;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

type SessionListener = (accessToken: string | null) => void;
let sessionListener: SessionListener | null = null;

/** AuthProvider registers here so a refreshed (or ended) session updates React state. */
export function setSessionListener(listener: SessionListener | null) {
  sessionListener = listener;
}

const refreshAccessToken = singleFlight(async (failedToken) => {
  // Another request may already have renewed the session.
  const current = getAccessToken();
  if (current && current !== failedToken) {
    return current;
  }
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).catch(() => null);
  if (!response?.ok) {
    // Only an explicit rejection ends the session; a network error leaves it for a later retry.
    if (response && (response.status === 401 || response.status === 403)) {
      clearTokens();
      sessionListener?.(null);
    }
    return null;
  }
  const tokens = (await response.json()) as TokenPair;
  saveTokens(tokens);
  sessionListener?.(tokens.access_token);
  return tokens.access_token;
});

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { accessToken, ...init } = options;
  const send = (token: string | null | undefined) => {
    const headers = new Headers(init.headers);
    if (!(init.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  };

  const response = await sendWithRefresh(send, accessToken, refreshAccessToken);

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new ApiError(body.detail ?? "Request failed", response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
