// Refresh-on-401 helpers. Kept free of Vite/DOM imports so they run under `node --test`.

/** Returns a new access token, or null when the session cannot be renewed. */
export type TokenRefresher = (failedToken: string) => Promise<string | null>;

/**
 * Collapse concurrent refreshes into one request. The backend rotates refresh
 * tokens, so two parallel refreshes would revoke each other's token.
 */
export function singleFlight(refresh: TokenRefresher): TokenRefresher {
  let inFlight: Promise<string | null> | null = null;
  return (failedToken) => {
    if (!inFlight) {
      inFlight = refresh(failedToken).finally(() => {
        inFlight = null;
      });
    }
    return inFlight;
  };
}

/**
 * Send a request; on 401 with a bearer token, refresh once and retry once.
 * A second 401, or a failed refresh, is returned to the caller unchanged.
 */
export async function sendWithRefresh(
  send: (accessToken: string | null | undefined) => Promise<Response>,
  accessToken: string | null | undefined,
  refresh: TokenRefresher,
): Promise<Response> {
  const response = await send(accessToken);
  if (response.status !== 401 || !accessToken) {
    return response;
  }
  const renewed = await refresh(accessToken);
  return renewed ? send(renewed) : response;
}
