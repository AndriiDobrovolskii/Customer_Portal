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
  // US-5.2 Plan Change 6: derived from POST /auth/login's own response shape
  // (LoginResponse vs MfaRequiredResponse) since no endpoint exposes an
  // `mfa_enabled`-shaped field (OD-5, OPEN) — SecurityScreen's real,
  // session-scoped basis for choosing enroll vs. disable. `false` here is a
  // documented default, not an implied fact about an unauthenticated caller:
  // /settings/security sits behind ProtectedRoute, so SecurityScreen never
  // renders while isAuthenticated is false.
  mfaEnabled: boolean;
}

interface SetSessionPayload {
  accessToken: string;
  user: UserRead;
  mfaEnrollmentDeadline?: string | null;
  // Required (not optional-with-`?? null`, unlike mfaEnrollmentDeadline) so
  // `tsc --noEmit` fails a build where either setSession call site
  // (useLogin.ts's direct branch, useMfaVerify.ts) forgets to pass it.
  mfaEnabled: boolean;
}

type Action =
  | { type: "SET_SESSION"; payload: SetSessionPayload }
  | { type: "SET_MFA_TOKEN"; token: string | null }
  | { type: "SET_MFA_ENABLED"; enabled: boolean }
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
        mfaEnabled: action.payload.mfaEnabled,
      };
    case "SET_MFA_TOKEN":
      return { ...state, mfaToken: action.token };
    case "SET_MFA_ENABLED":
      return { ...state, mfaEnabled: action.enabled };
    case "TOKEN_REFRESHED":
      return { ...state, accessToken: action.accessToken };
    case "CLEAR_SESSION":
      return {
        accessToken: null,
        isAuthenticated: false,
        user: null,
        mfaToken: null,
        mfaEnrollmentDeadline: null,
        mfaEnabled: false,
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
  mfaEnabled: false,
};

export interface AuthStoreValue extends AuthStateSeed {
  setSession: (session: SetSessionPayload) => void;
  setMfaToken: (token: string | null) => void;
  setMfaEnabled: (enabled: boolean) => void;
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
  const setMfaEnabled = useCallback((enabled: boolean) => {
    dispatch({ type: "SET_MFA_ENABLED", enabled });
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
    () => ({ ...state, setSession, setMfaToken, setMfaEnabled, clearSession }),
    [state, setSession, setMfaToken, setMfaEnabled, clearSession],
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
