import { createContext, useContext, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getCurrentUser } from "../../api/auth";
import type { TokenPair, User } from "../../types/auth";
import { clearTokens, getAccessToken, saveTokens } from "./tokenStorage";

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
        clearTokens();
        setAccessToken(null);
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
