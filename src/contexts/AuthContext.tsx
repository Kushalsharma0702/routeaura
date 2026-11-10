/**
 * Authentication context backed by the RouteAura API.
 * The session is restored on load from the HttpOnly refresh cookie; nothing sensitive
 * is kept in localStorage. Authorization is enforced by the server; the `role` here
 * only decides which UI to show.
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { authApi, type RegisterInput } from '@/lib/api/auth';
import { ApiError, setSessionExpiredHandler, type ApiUser } from '@/lib/api/client';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  phone?: string;
  role: 'admin' | 'client'; // backend "traveler" is presented as "client" in the UI
  joinedDate: string;
}

export function toAuthUser(u: ApiUser): AuthUser {
  return {
    id: u.id,
    name: u.full_name,
    email: u.email,
    phone: u.phone ?? undefined,
    role: u.role === 'admin' ? 'admin' : 'client',
    joinedDate: u.created_at.slice(0, 10),
  };
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  /** Resolves to null on success, or a user-facing error message. */
  login: (email: string, password: string) => Promise<string | null>;
  register: (input: RegisterInput) => Promise<string | null>;
  logout: () => Promise<void>;
  setUser: (u: AuthUser) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

function messageFor(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === 'validation_error' && Array.isArray(err.details) && err.details[0]) {
      return String(err.details[0].message).replace(/^Value error, /, '');
    }
    return err.message;
  }
  return 'Cannot reach the server. Please try again.';
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    authApi.restore().then(u => {
      if (active) { setUser(u ? toAuthUser(u) : null); setIsLoading(false); }
    });
    setSessionExpiredHandler(() => setUser(null));
    return () => { active = false; setSessionExpiredHandler(null); };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    try { setUser(toAuthUser(await authApi.login(email, password))); return null; }
    catch (e) { return messageFor(e); }
  }, []);

  const register = useCallback(async (input: RegisterInput) => {
    try { setUser(toAuthUser(await authApi.register(input))); return null; }
    catch (e) { return messageFor(e); }
  }, []);

  const logout = useCallback(async () => {
    try { await authApi.logout(); } catch { /* session is cleared locally regardless */ }
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, isAuthenticated: !!user, isLoading, login, register, logout, setUser }),
    [user, isLoading, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
