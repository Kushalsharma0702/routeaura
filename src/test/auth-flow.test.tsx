import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '@/contexts/AuthContext';
import Login from '@/pages/Login';
import { tokenStore } from '@/lib/api/client';

const apiUser = (role: 'traveler' | 'admin') => ({
  id: 'u1', email: 'a@b.co', full_name: 'Asha Rao', phone: null, role, is_active: true,
  created_at: '2026-01-02T00:00:00Z',
});
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
const session = (role: 'traveler' | 'admin') => ({ access_token: 't', expires_in: 900, user: apiUser(role) });

function setup(handler: (url: string, init?: RequestInit) => Response) {
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => handler(url, init)));
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<LandingProbe />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
function LandingProbe() {
  const { user } = useAuth();
  return user ? <Navigate to={user.role === 'admin' ? '/admin-home' : '/client-home'} replace /> : null;
}

describe('Login / registration against the API', () => {
  beforeEach(() => tokenStore.set(null));
  afterEach(() => vi.unstubAllGlobals());

  const noSession = (url: string) =>
    url.endsWith('/auth/refresh') ? json(401, { error: { code: 'invalid_refresh', message: 'Session expired' } }) : json(404, {});

  it('shows client-side validation errors without calling the API', async () => {
    const user = userEvent.setup();
    setup(noSession);
    await user.click(await screen.findByRole('button', { name: 'Sign In' }));
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument();
    expect(screen.getByText('Password is required')).toBeInTheDocument();
  });

  it('shows the server error for bad credentials', async () => {
    const user = userEvent.setup();
    setup(url => url.endsWith('/auth/login')
      ? json(401, { error: { code: 'invalid_credentials', message: 'Invalid email or password' } })
      : noSession(url));
    await user.type(await screen.findByLabelText('Email'), 'a@b.co');
    await user.type(screen.getByLabelText('Password'), 'wrongpass1');
    await user.click(screen.getByRole('button', { name: 'Sign In' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password');
    expect(tokenStore.get()).toBeNull();
  });

  it('logs in and stores the access token in memory only', async () => {
    const user = userEvent.setup();
    setup(url => url.endsWith('/auth/login') ? json(200, session('traveler')) : noSession(url));
    await user.type(await screen.findByLabelText('Email'), 'a@b.co');
    await user.type(screen.getByLabelText('Password'), 'Passw0rd1');
    await user.click(screen.getByRole('button', { name: 'Sign In' }));
    await waitFor(() => expect(tokenStore.get()).toBe('t'));
  });

  it('registers a new traveler with the entered details', async () => {
    const user = userEvent.setup();
    const calls: { url: string; body?: string }[] = [];
    setup((url, init) => {
      calls.push({ url, body: init?.body as string | undefined });
      return url.endsWith('/auth/register') ? json(201, session('traveler')) : noSession(url);
    });
    await user.click(await screen.findByRole('button', { name: 'Create an account' }));
    await user.type(screen.getByLabelText('Full name'), 'Asha Rao');
    await user.type(screen.getByLabelText('Email'), 'a@b.co');
    await user.type(screen.getByLabelText('Password'), 'Passw0rd1');
    await user.click(screen.getByRole('button', { name: 'Create Account' }));
    await waitFor(() => expect(calls.some(c => c.url.endsWith('/auth/register'))).toBe(true));
    const reg = calls.find(c => c.url.endsWith('/auth/register'))!;
    expect(JSON.parse(reg.body!)).toMatchObject({ email: 'a@b.co', full_name: 'Asha Rao', password: 'Passw0rd1' });
  });

  it('rejects a weak password in the register form', async () => {
    const user = userEvent.setup();
    setup(noSession);
    await user.click(await screen.findByRole('button', { name: 'Create an account' }));
    await user.type(screen.getByLabelText('Full name'), 'Asha');
    await user.type(screen.getByLabelText('Email'), 'a@b.co');
    await user.type(screen.getByLabelText('Password'), 'short');
    await user.click(screen.getByRole('button', { name: 'Create Account' }));
    expect(await screen.findByText('At least 8 characters')).toBeInTheDocument();
  });
});
