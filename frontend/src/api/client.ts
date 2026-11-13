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

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (options.accessToken) {
    headers.set("Authorization", `Bearer ${options.accessToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    const detail: unknown = body.detail;
    const message = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map((issue) => `${issue.loc?.slice(1).join(".") ?? "Input"}: ${issue.msg ?? "Invalid value"}`).join("; ")
      : detail && typeof detail === "object" && "message" in detail ? String(detail.message)
      : "Request failed";
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
