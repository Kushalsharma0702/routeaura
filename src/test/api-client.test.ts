import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiFetch, setSessionExpiredHandler, tokenStore } from '@/lib/api/client';

const json = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
const authBody = { access_token: 'new-token', expires_in: 900, user: {} };

describe('apiFetch', () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
    tokenStore.set('old-token');
    setSessionExpiredHandler(null);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('sends the bearer token and parses JSON', async () => {
    fetchMock.mockResolvedValueOnce(json(200, { ok: true }));
    await expect(apiFetch('/ping')).resolves.toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/ping');
    expect(init.headers.Authorization).toBe('Bearer old-token');
    expect(init.credentials).toBe('include');
  });

  it('turns server errors into ApiError with code and message', async () => {
    fetchMock.mockResolvedValueOnce(json(409, { error: { code: 'email_taken', message: 'taken' } }));
    const err = await apiFetch('/x', { skipAuthRefresh: true }).catch(e => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 409, code: 'email_taken', message: 'taken' });
  });

  it('refreshes once on 401 then retries with the new token', async () => {
    fetchMock
      .mockResolvedValueOnce(json(401, { error: { code: 'invalid_token', message: 'x' } }))
      .mockResolvedValueOnce(json(200, authBody)) // refresh
      .mockResolvedValueOnce(json(200, { data: 1 }));
    await expect(apiFetch('/me')).resolves.toEqual({ data: 1 });
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/auth/refresh');
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe('Bearer new-token');
  });

  it('shares ONE refresh between concurrent 401s (rotating tokens must not be replayed)', async () => {
    let refreshes = 0;
    fetchMock.mockImplementation(async (url: string, init: RequestInit & { headers: Record<string, string> }) => {
      if (url === '/api/v1/auth/refresh') { refreshes++; return json(200, authBody); }
      return init.headers.Authorization === 'Bearer new-token' ? json(200, { ok: 1 }) : json(401, { error: { code: 'invalid_token', message: 'x' } });
    });
    await Promise.all([apiFetch('/a'), apiFetch('/b'), apiFetch('/c')]);
    expect(refreshes).toBe(1);
  });

  it('clears the token and signals expiry when refresh fails', async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    fetchMock.mockResolvedValueOnce(json(401, { error: { code: 'invalid_token', message: 'x' } }))
      .mockResolvedValueOnce(json(401, { error: { code: 'invalid_refresh', message: 'x' } }));
    await expect(apiFetch('/me')).rejects.toMatchObject({ status: 401 });
    expect(tokenStore.get()).toBeNull();
    expect(expired).toHaveBeenCalledOnce();
  });
});
