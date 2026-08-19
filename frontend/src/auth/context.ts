import { createContext, useContext } from 'react';

// Dashboard session state. The JWT lives in sessionStorage: it survives a
// reload but dies with the tab. Not localStorage, because the token is a
// 60-minute bearer with no refresh path, so outliving the browser buys nothing
// and only widens the window to steal it. Rotation arrives with #51.

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
