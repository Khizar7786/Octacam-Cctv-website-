import { createContext, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { browserApiClient } from "~/lib/api/browser-client";
import { AuthRuntime, type AuthState } from "./runtime";

const AuthContext = createContext<{ state: AuthState; runtime: AuthRuntime } | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // Each SSR render receives an isolated, empty instance. Only the browser effect uses its cookie.
  const [runtime] = useState(() => new AuthRuntime(browserApiClient));
  const state = useSyncExternalStore(runtime.subscribe, runtime.getState, runtime.getServerSnapshot);
  useEffect(() => { void runtime.restore(); }, [runtime]);
  return <AuthContext.Provider value={{ state, runtime }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("AuthProvider is required for session controls.");
  return context;
}
