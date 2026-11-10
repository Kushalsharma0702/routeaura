import { apiFetch, refreshSession, tokenStore, type ApiUser, type AuthResponse } from './client';

export interface RegisterInput { email: string; password: string; full_name: string; phone?: string }

async function withToken(p: Promise<AuthResponse>): Promise<ApiUser> {
  const res = await p;
  tokenStore.set(res.access_token);
  return res.user;
}

export const authApi = {
  register: (input: RegisterInput) =>
    withToken(apiFetch<AuthResponse>('/auth/register', { method: 'POST', body: input, skipAuthRefresh: true })),
  login: (email: string, password: string) =>
    withToken(apiFetch<AuthResponse>('/auth/login', { method: 'POST', body: { email, password }, skipAuthRefresh: true })),
  /** Restores a session from the HttpOnly refresh cookie; resolves null when there is none. */
  restore: async (): Promise<ApiUser | null> => (await refreshSession())?.user ?? null,
  logout: async () => {
    try {
      await apiFetch<void>('/auth/logout', { method: 'POST', skipAuthRefresh: true });
    } finally {
      tokenStore.set(null);
    }
  },
};
