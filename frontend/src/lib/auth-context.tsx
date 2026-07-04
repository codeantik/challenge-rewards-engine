"use client";

import { createContext, useCallback, useContext, useMemo, useSyncExternalStore } from "react";

import { AUTH_UNAUTHORIZED_EVENT } from "@/lib/api";
import { type AuthUser, loginUser, registerUser } from "@/lib/auth-api";
import { AUTH_STORAGE_KEY } from "@/lib/config";

interface StoredSession {
  token: string;
  user: AuthUser;
}

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** `localStorage` is an external store React doesn't know about, so reads
 * go through `useSyncExternalStore` rather than "read in an effect, then
 * setState" — that pattern causes a cascading extra render (and is what
 * the `react-hooks/set-state-in-effect` lint rule flags) and, worse here,
 * a real hydration mismatch: the server always renders as logged-out (no
 * `window`), so a naive effect-driven update flips the UI a tick *after*
 * commit. `useSyncExternalStore`'s `getServerSnapshot` makes "unknown yet"
 * an explicit third state (`loading`) instead of quietly aliasing it to
 * `unauthenticated`, which is what stops an already-logged-in user from
 * flashing through `/login` on a hard refresh. */
const AUTH_CHANGED_EVENT = "cre:auth-changed";

function getSnapshot(): string | null {
  return window.localStorage.getItem(AUTH_STORAGE_KEY);
}

function getServerSnapshot(): undefined {
  return undefined;
}

function subscribe(callback: () => void): () => void {
  function handleUnauthorized() {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    callback();
  }
  window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
  window.addEventListener(AUTH_CHANGED_EVENT, callback);
  return () => {
    window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    window.removeEventListener(AUTH_CHANGED_EVENT, callback);
  };
}

function writeSession(next: StoredSession | null): void {
  if (next) {
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(next));
  } else {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  }
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

function parseSession(raw: string | null | undefined): StoredSession | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const raw = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const session = useMemo(() => parseSession(raw), [raw]);
  const status: AuthStatus =
    raw === undefined ? "loading" : session ? "authenticated" : "unauthenticated";

  const login = useCallback(async (email: string, password: string) => {
    const result = await loginUser(email, password);
    writeSession({ token: result.access_token, user: result.user });
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const result = await registerUser(email, password);
    writeSession({ token: result.access_token, user: result.user });
  }, []);

  const logout = useCallback(() => {
    writeSession(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user: session?.user ?? null,
        token: session?.token ?? null,
        status,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
