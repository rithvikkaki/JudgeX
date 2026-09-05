import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, tokenStore } from "./api";
import type { User } from "./types";

interface AuthValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore the session on boot. A stored token may have expired while the
  // tab was closed, so it is validated against the server rather than trusted.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (!tokenStore.get()) {
        setLoading(false);
        return;
      }
      try {
        const me = await api.me();
        if (!cancelled) setUser(me);
      } catch {
        tokenStore.clear();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // The API client broadcasts this when any request comes back 401, so an
  // expired token clears the UI immediately instead of on next navigation.
  useEffect(() => {
    const onUnauthorised = () => setUser(null);
    window.addEventListener("judgex:unauthorised", onUnauthorised);
    window.addEventListener("crucible:unauthorised", onUnauthorised);
    return () => {
      window.removeEventListener("judgex:unauthorised", onUnauthorised);
      window.removeEventListener("crucible:unauthorised", onUnauthorised);
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.login({ email, password });
    tokenStore.set(result.access_token);
    setUser(result.user);
  }, []);

  const register = useCallback(
    async (username: string, email: string, password: string) => {
      const result = await api.register({ username, email, password });
      tokenStore.set(result.access_token);
      setUser(result.user);
    },
    [],
  );

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside an AuthProvider");
  return context;
}
