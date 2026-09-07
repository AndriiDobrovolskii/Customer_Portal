// Auth store (Client State Notes, docs/specifications/US-5.1-spec.md):
// `accessToken` in memory only (never localStorage/sessionStorage — spec
// NFR), `isAuthenticated`, current `user`, and a transient `mfaToken` held
// only between the MFA-required response and the verify call. React Context
// per docs/plans/US-5.1-implementation-plan.md Architectural Change 4 (no
// new state-management dependency). Imports neither `api/` nor `hooks/`
// directly (AGENTS.md §3's `store/` row) — the one exception is the neutral
// `session/sessionBridge` seam (see that file's own header comment), which
// is not `api/` itself and holds no fetch/business logic.
import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from "react";
import type { ReactNode } from "react";
import { configureSessionBridge, resetSessionBridge } from "../session/sessionBridge";
import type { UserRead } from "../api/types";

export interface AuthStateSeed {
  accessToken: string | null;
  isAuthenticated: boolean;
  user: UserRead | null;
  mfaToken: string | null;
  mfaEnrollmentDeadline: string | null;
}

interface SetSessionPayload {
  accessToken: string;
  user: UserRead;
  mfaEnrollmentDeadline?: string | null;
}

type Action =
  | { type: "SET_SESSION"; payload: SetSessionPayload }
  | { type: "SET_MFA_TOKEN"; token: string | null }
  | { type: "TOKEN_REFRESHED"; accessToken: string }
  | { type: "CLEAR_SESSION" };

function reducer(state: AuthStateSeed, action: Action): AuthStateSeed {
  switch (action.type) {
    case "SET_SESSION":
      return {
        accessToken: action.payload.accessToken,
        isAuthenticated: true,
        user: action.payload.user,
        mfaToken: null,
        mfaEnrollmentDeadline: action.payload.mfaEnrollmentDeadline ?? null,
      };
    case "SET_MFA_TOKEN":
      return { ...state, mfaToken: action.token };
    case "TOKEN_REFRESHED":
      return { ...state, accessToken: action.accessToken };
    case "CLEAR_SESSION":
      return {
        accessToken: null,
        isAuthenticated: false,
        user: null,
        mfaToken: null,
        mfaEnrollmentDeadline: null,
      };
    default:
      return state;
  }
}

const defaultState: AuthStateSeed = {
  accessToken: null,
  isAuthenticated: false,
  user: null,
  mfaToken: null,
  mfaEnrollmentDeadline: null,
};

export interface AuthStoreValue extends AuthStateSeed {
  setSession: (session: SetSessionPayload) => void;
  setMfaToken: (token: string | null) => void;
  clearSession: () => void;
}

const AuthContext = createContext<AuthStoreValue | null>(null);

export interface AuthProviderProps {
  children: ReactNode;
  /** Test-only seam: seeds a starting session without a real login call. */
  initialState?: AuthStateSeed;
}

export function AuthProvider({ children, initialState }: AuthProviderProps) {
  const [state, dispatch] = useReducer(reducer, initialState ?? defaultState);

  const setSession = useCallback((session: SetSessionPayload) => {
    dispatch({ type: "SET_SESSION", payload: session });
  }, []);
  const setMfaToken = useCallback((token: string | null) => {
    dispatch({ type: "SET_MFA_TOKEN", token });
  }, []);
  const clearSession = useCallback(() => {
    dispatch({ type: "CLEAR_SESSION" });
  }, []);

  // Kept current on every render so the session bridge (read imperatively by
  // `api/httpClient.ts`, never as a React hook) always sees the latest token
  // without a stale closure.
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    configureSessionBridge({
      getAccessToken: () => stateRef.current.accessToken,
      onTokenRefreshed: (accessToken: string) => dispatch({ type: "TOKEN_REFRESHED", accessToken }),
      onSessionExpired: () => dispatch({ type: "CLEAR_SESSION" }),
    });
    return () => resetSessionBridge();
  }, []);

  const value = useMemo<AuthStoreValue>(
    () => ({ ...state, setSession, setMfaToken, clearSession }),
    [state, setSession, setMfaToken, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthStore(): AuthStoreValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuthStore must be used within an AuthProvider");
  }
  return context;
}
