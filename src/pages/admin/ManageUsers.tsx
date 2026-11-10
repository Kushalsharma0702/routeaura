import { useState } from 'react';
import { motion } from 'framer-motion';
import { Mail, Phone, Calendar, Search } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { ApiError } from '@/lib/api/client';
import { useAdminUpdateUser, useAdminUsers } from '@/hooks/useUsers';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';

export default function ManageUsers() {
  const { user: me } = useAuth();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useAdminUsers(search, page);
  const update = useAdminUpdateUser();

  const run = (id: string, patch: { role?: 'traveler' | 'admin'; is_active?: boolean }, ok: string) =>
    update.mutate({ id, ...patch }, {
      onSuccess: () => toast.success(ok),
      onError: e => toast.error(e instanceof ApiError ? e.message : 'Update failed'),
    });

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Manage Users</h1>
        <p className="text-sm text-muted-foreground mt-1">{data ? `${data.total} registered users` : 'Loading users…'}</p>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input aria-label="Search users" placeholder="Search name or email…" value={search} className="pl-9"
          onChange={e => { setSearch(e.target.value); setPage(1); }} />
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[0, 1, 2].map(i => <Skeleton key={i} className="h-44 rounded-xl" />)}
        </div>
      )}
      {isError && (
        <div className="rounded-xl border border-border/50 p-6 text-sm">
          Could not load users. <Button variant="link" onClick={() => refetch()}>Retry</Button>
        </div>
      )}
      {data && data.items.length === 0 && <p className="text-sm text-muted-foreground">No users match your search.</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {data?.items.map((u, i) => {
          const isSelf = u.id === me?.id;
          return (
            <motion.div key={u.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
              className="bg-card rounded-xl border border-border/50 shadow-card p-6">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-full gradient-primary flex items-center justify-center text-lg font-bold text-primary-foreground">
                  {u.full_name.charAt(0)}
                </div>
                <div className="min-w-0">
                  <h3 className="font-semibold text-card-foreground truncate">{u.full_name}</h3>
                  <div className="flex gap-2 mt-1">
                    <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full capitalize">{u.role}</span>
                    {!u.is_active && <span className="text-xs bg-destructive/10 text-destructive px-2 py-0.5 rounded-full">Disabled</span>}
                  </div>
                </div>
              </div>
              <div className="space-y-2 text-sm text-muted-foreground">
                <div className="flex items-center gap-2"><Mail className="w-4 h-4 shrink-0" /><span className="truncate">{u.email}</span></div>
                {u.phone && <div className="flex items-center gap-2"><Phone className="w-4 h-4" />{u.phone}</div>}
                <div className="flex items-center gap-2"><Calendar className="w-4 h-4" />Joined {u.created_at.slice(0, 10)}</div>
              </div>
              <div className="flex gap-2 mt-4">
                <Button size="sm" variant="outline" disabled={isSelf || update.isPending} className="text-xs"
                  onClick={() => run(u.id, { role: u.role === 'admin' ? 'traveler' : 'admin' },
                    u.role === 'admin' ? 'Admin rights removed' : 'User promoted to admin')}>
                  {u.role === 'admin' ? 'Remove admin' : 'Make admin'}
                </Button>
                <Button size="sm" variant="outline" disabled={isSelf || update.isPending} className="text-xs"
                  onClick={() => run(u.id, { is_active: !u.is_active }, u.is_active ? 'User disabled' : 'User enabled')}>
                  {u.is_active ? 'Disable' : 'Enable'}
                </Button>
              </div>
            </motion.div>
          );
        })}
      </div>

      {data && pages > 1 && (
        <div className="flex items-center gap-3">
          <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
          <span className="text-sm text-muted-foreground">Page {page} of {pages}</span>
          <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      )}
    </div>
  );
}
