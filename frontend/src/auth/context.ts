import { createContext, useContext } from 'react';

// Dashboard session state. The JWT lives in memory only, never localStorage,
// so a page reload drops the login. Refresh tokens are deferred to M6.

export type Role = 'admin' | 'operator';

export interface Session {
  token: string;
  username: string;
  role: Role;
}

export interface AuthContextValue {
  session: Session | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
