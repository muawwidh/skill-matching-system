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

export function getCurrentUser(accessToken: string) {
  return apiRequest<User>("/auth/me", { accessToken });
}
