import { apiRequest } from "./client";
import type { LoginPayload, RegisterPayload, TokenPair, User } from "../types/auth";

export function register(payload: RegisterPayload) {
  return apiRequest<TokenPair>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function login(payload: LoginPayload) {
  return apiRequest<TokenPair>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Revokes the refresh token on the server (sign-out). */
export function logout(refreshToken: string) {
  return apiRequest<void>("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export function getCurrentUser(accessToken: string) {
  return apiRequest<User>("/auth/me", { accessToken });
}

/** Deletes the signed-in candidate's account and all of its data (password confirmation). */
export function deleteAccount(accessToken: string, password: string) {
  return apiRequest<void>("/auth/delete-account", {
    method: "POST",
    accessToken,
    body: JSON.stringify({ password }),
  });
}
