# Repository Audit (Milestone 0)

Audited 2026-11-11 at commit `1704f8d` (identical to `origin/main`, `Kushalsharma0702/routeaura`).

## 1. What the repository is

A **front-end-only** Vite + React 18 + TypeScript + Tailwind + shadcn/ui prototype (originally generated with Lovable; `lovable-tagger` is a dev dependency).
There is **no backend, no database, no API calls**. 99 tracked files, ~1,800 lines of page code, plus 50 generated shadcn/ui primitives.

## 2. Feature inventory

| Area | Files | Real behaviour today |
|---|---|---|
| Landing | `pages/Index.tsx` | Redirect only |
| Auth | `pages/Login.tsx`, `contexts/AuthContext.tsx` | Two hardcoded credential pairs checked **in the browser**; user object stored in `localStorage`. No registration. Not secure; must be replaced. |
| Routing / guards | `App.tsx` | React Router v6; `ProtectedRoute` checks the client-side role (`admin` / `client`). |
| Layout | `components/layouts/DashboardLayout.tsx`, `MobileBottomNav.tsx` | Responsive sidebar + bottom nav, role-based menus. Reusable as is. |
| Client: dashboard | `pages/client/ClientDashboard.tsx` | Stat cards and lists computed from mock arrays. |
| Client: browse packages | `pages/client/BrowsePackages.tsx` | Search + budget/duration filters work (client-side). **"Book" only shows a success toast; nothing is created.** |
| Client: my bookings | `pages/client/MyBookings.tsx` | Lists mock bookings; cancel mutates component state only (lost on refresh). |
| Client: profile | `pages/client/ClientProfile.tsx` | Form UI; not persisted. |
| Admin: dashboard | `pages/admin/AdminDashboard.tsx` | Recharts over hardcoded `monthlyBookingsData` / `destinationData`. |
| Admin: packages / destinations / routes | `pages/admin/Manage*.tsx` | CRUD on **component state** seeded from mock data. Lost on refresh. |
| Admin: bookings | `pages/admin/ManageBookings.tsx` | Approve/reject mutates component state only. |
| Admin: users | `pages/admin/ManageUsers.tsx` | Read-only list of demo users. |
| Data | `data/mockData.ts` (312 lines) | 5 users, 6 packages, 5 destinations, 6 routes, 5 bookings, chart series. |

**Not present at all:** recommendations, itinerary generation, optimization, context engine, voice/multilingual, hotels/rooms/inventory, notifications, maps, payments, analytics beyond static charts, any test beyond a placeholder.

## 3. Dependency and build audit

| Check | Result |
|---|---|
| `npm run build` as found | **Failed.** `node_modules` had been installed for Linux (`@rollup/rollup-linux-x64-gnu`) on an arm64 Mac, so rollup's native module was missing. Fix: `rm -rf node_modules && npm ci` (regenerable, gitignored). |
| `npm run build` after reinstall | Passes. One 1.0 MB JS chunk (no code splitting). |
| `npm test` | 1 placeholder test passes. No real tests exist. |
| `npm run lint` | **3 errors, 8 warnings.** Errors: empty interface in `ui/command.tsx` and `ui/textarea.tsx`; `require()` in `tailwind.config.ts`. Warnings: react-refresh export rules in shadcn files. |
| TanStack Query | Installed and `QueryClientProvider` mounted, but **no `useQuery`/`useMutation` anywhere**. |
| react-hook-form + zod | Installed; forms use plain `useState` instead. |
| Lockfiles | Both `package-lock.json` and `bun.lockb` are committed. npm is the one used here. Pick one (npm). |
| Unused / not needed | `lovable-tagger` (Lovable-specific), many shadcn primitives that no page imports (left alone: removing them is churn with no benefit). |
| Not installed yet | Map library (Leaflet), Zustand (only add if needed), i18n library. |

## 4. Local environment found

| Tool | State |
|---|---|
| Node 26.13, npm | present |
| Python | system `python@3.15` only (too new for several scientific wheels). **`uv` is present**, so a pinned Python 3.12 will be provisioned by `uv`. |
| PostgreSQL | `postgresql@18` (Homebrew) running on `localhost:5432` |
| Docker | Desktop installed and daemon running |
| Redis | not installed locally; run via Docker Compose |

## 5. Existing problems, recorded before any change

1. Authentication is client-side only and trivially bypassable.
2. All state is non-persistent; every admin "save" is lost on refresh.
3. Dead or fake actions: client "Book" (toast only), profile save, parts of admin forms.
4. Role named `client` in the front end; the spec calls the role `traveler`.
5. Money values are plain numbers in INR with no currency field; distances/durations in routes are free-text strings (`'1,025 km'`, `'2 days'`), which cannot be used by an optimizer.
6. Destinations have no coordinates, categories, cost, duration or climate, and attractions are bare strings. The recommender and optimizer need structured data.
7. Images are remote Unsplash URLs (availability not guaranteed).
8. Source comments call the product "Escapade Central" in places; the product name is RouteAura.
9. Lint errors and the oversized bundle noted above.

## 6. Preservation decisions

Keep: all pages, layouts, UI primitives, theme, routing structure, framer-motion animations.
Change in place: swap `mockData` imports for typed API hooks page by page, starting with auth (Milestone 1) then destinations (Milestone 2).
Do not delete: any existing page or feature.
