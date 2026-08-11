import { useCallback, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { AuthContext } from './context';
import type { Role, Session } from './context';

const STORAGE_KEY = 'ota.session';

// Decoding without verifying is fine: the backend re-verifies on every request.
// The claims only decide what the UI offers, never what it is allowed to do.
function tokenClaims(token: string): { role?: string; exp?: number } | null {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch {
    return null;
  }
}

function roleFromToken(token: string): Role {
  return tokenClaims(token)?.role === 'admin' ? 'admin' : 'operator';
}

// The inverse of storeSession. Anything unusable is dropped rather than
// repaired: restoring an expired token would render a logged-in shell whose
// every request 401s, with no login form in reach.
function readStoredSession(): Session | null {
  const stored = sessionStorage.getItem(STORAGE_KEY);
  if (!stored) return null;

  try {
    const { token, username, role } = JSON.parse(stored);
    if (typeof token !== 'string' || typeof username !== 'string') throw new Error('bad shape');

    const exp = tokenClaims(token)?.exp;
    if (typeof exp !== 'number' || exp * 1000 <= Date.now()) throw new Error('expired');

    return { token, username, role: role === 'admin' ? 'admin' : 'operator' };
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function storeSession(session: Session | null) {
  if (session) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  else sessionStorage.removeItem(STORAGE_KEY);
}

async function errorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // Non-JSON body; use the fallback.
  }
  return fallback;
}

export default function AuthProvider({ children }: { children: ReactNode }) {
  // Restored during the first render, not in an effect: RequireAuth redirects
  // to /login the moment it sees a null session, and would win that race.
  const [session, setSessionState] = useState<Session | null>(readStoredSession);

  const setSession = useCallback((next: Session | null) => {
    storeSession(next);
    setSessionState(next);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch('/backend/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      throw new Error(await errorDetail(res, `Login failed (HTTP ${res.status})`));
    }
    const { access_token } = await res.json();
    setSession({ token: access_token, username, role: roleFromToken(access_token) });
  }, [setSession]);

  const register = useCallback(async (username: string, password: string) => {
    const res = await fetch('/backend/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      throw new Error(await errorDetail(res, `Registration failed (HTTP ${res.status})`));
    }
  }, []);

  const logout = useCallback(() => setSession(null), [setSession]);

  const value = useMemo(
    () => ({ session, login, register, logout }),
    [session, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
