/**
 * Central HTTP client. All backend access goes through here (never fetch() in components).
 * - Access token lives in memory only; the refresh token is an HttpOnly cookie.
 * - On a 401, a single shared refresh is attempted once, then the request is retried.
 */
export const API_BASE = '/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;

export const tokenStore = {
  set: (t: string | null) => { accessToken = t; },
  get: () => accessToken,
};
export const setSessionExpiredHandler = (fn: (() => void) | null) => { onSessionExpired = fn; };

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined | null>;
  skipAuthRefresh?: boolean;
}

export interface AuthResponse {
  access_token: string;
  expires_in: number;
  user: ApiUser;
}
export interface ApiUser {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: 'traveler' | 'admin';
  is_active: boolean;
  created_at: string;
}

let refreshInFlight: Promise<AuthResponse | null> | null = null;

/**
 * Single-flight refresh. Refresh tokens rotate, so two concurrent refreshes with the same
 * cookie would look like token theft to the server; every caller must share one request.
 */
export function refreshSession(): Promise<AuthResponse | null> {
  refreshInFlight ??= (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, { method: 'POST', credentials: 'include' });
      if (!res.ok) return null;
      const data = (await res.json()) as AuthResponse;
      accessToken = data.access_token;
      return data;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const e = body?.error;
    return new ApiError(res.status, e?.code ?? 'error', e?.message ?? res.statusText, e?.details);
  } catch {
    return new ApiError(res.status, 'error', res.statusText || 'Request failed');
  }
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { body, params, skipAuthRefresh, headers, ...rest } = opts;
  const qs = params
    ? '?' + new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
          .map(([k, v]) => [k, String(v)]),
      ).toString()
    : '';

  const doFetch = () => fetch(`${API_BASE}${path}${qs}`, {
    ...rest,
    credentials: 'include',
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const usedToken = accessToken;
  let res = await doFetch();
  if (res.status === 401 && !skipAuthRefresh) {
    // If another request already refreshed while ours was in flight, just retry with the new token.
    if (accessToken !== usedToken || (await refreshSession())) {
      res = await doFetch();
    } else {
      accessToken = null;
      onSessionExpired?.();
    }
  }
  if (!res.ok) throw await parseError(res);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
