import { useCallback, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { AuthContext } from './context';
import type { Role, Session } from './context';

// The role claim drives what the UI offers (upload is admin-only). Decoding
// without verifying is fine: the backend re-verifies on every request.
function roleFromToken(token: string): Role {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.role === 'admin' ? 'admin' : 'operator';
  } catch {
    return 'operator';
  }
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
  const [session, setSession] = useState<Session | null>(null);

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
  }, []);

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

  const logout = useCallback(() => setSession(null), []);

  const value = useMemo(
    () => ({ session, login, register, logout }),
    [session, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
