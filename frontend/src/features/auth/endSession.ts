/**
 * Sign out: forget the tokens in this browser at once, then ask the server to revoke the refresh token so it
 * cannot be used again. A failed revoke (offline, token already expired) does not keep the user signed in.
 */
export async function endSession(
  refreshToken: string | null,
  clearLocal: () => void,
  revoke: (refreshToken: string) => Promise<unknown>,
): Promise<void> {
  clearLocal();
  if (!refreshToken) return;
  try {
    await revoke(refreshToken);
  } catch {
    // The local session is already gone; an unrevoked token still expires on its own.
  }
}
