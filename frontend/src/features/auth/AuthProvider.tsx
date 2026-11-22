import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getCurrentUser, logout } from "../../api/auth";
import { setSessionListener } from "../../api/client";
import type { TokenPair, User } from "../../types/auth";
import { endSession } from "./endSession";
import { clearTokens, getAccessToken, getRefreshToken, saveTokens } from "./tokenStorage";

type AuthContextValue = {
  accessToken: string | null;
  user: User | undefined;
  isAuthenticated: boolean;
  setSession: (tokens: TokenPair) => void;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(() => getAccessToken());

  // The API client renews an expired access token on 401; mirror the result here.
  useEffect(() => {
    setSessionListener(setAccessToken);
    return () => setSessionListener(null);
  }, []);

  const userQuery = useQuery({
    queryKey: ["current-user", accessToken],
    queryFn: () => getCurrentUser(accessToken as string),
    enabled: Boolean(accessToken),
    retry: false,
  });

  const value = useMemo<AuthContextValue>(
    () => ({
      accessToken,
      user: userQuery.data,
      isAuthenticated: Boolean(accessToken),
      setSession(tokens) {
        saveTokens(tokens);
        setAccessToken(tokens.access_token);
      },
      signOut() {
        void endSession(getRefreshToken(), () => { clearTokens(); setAccessToken(null); }, logout);
      },
    }),
    [accessToken, userQuery.data],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
