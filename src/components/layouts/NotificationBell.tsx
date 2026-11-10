import { Link } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { useMarkAllRead, useMarkRead, useNotifications, useUnreadCount } from '@/hooks/useNotifications';

export default function NotificationBell() {
  const unread = useUnreadCount();
  const list = useNotifications({ page: 1, page_size: 5 });
  const mark = useMarkRead();
  const markAll = useMarkAllRead();
  const n = unread.data?.unread ?? 0;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative w-9 h-9" aria-label={n ? `Notifications, ${n} unread` : 'Notifications'}>
          <Bell className="w-5 h-5 text-muted-foreground" />
          {n > 0 && <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-accent text-accent-foreground text-[10px] font-semibold flex items-center justify-center" aria-hidden>{n > 9 ? '9+' : n}</span>}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <div className="flex items-center justify-between px-2 py-1.5"><span className="text-sm font-medium">Notifications</span>
          <Button variant="link" size="sm" className="h-auto p-0 text-xs" disabled={n === 0 || markAll.isPending} onClick={() => markAll.mutate()}>Mark all read</Button></div>
        <DropdownMenuSeparator />
        {list.isLoading && <p className="px-2 py-3 text-xs text-muted-foreground" role="status">Loading…</p>}
        {list.isError && <p className="px-2 py-3 text-xs text-destructive" role="alert">Could not load notifications.</p>}
        {list.data?.items.length === 0 && <p className="px-2 py-3 text-xs text-muted-foreground">You're all caught up.</p>}
        {list.data?.items.map(x => (
          <DropdownMenuItem key={x.id} className="flex-col items-start gap-0.5 whitespace-normal cursor-pointer" onSelect={() => { if (!x.read_at) mark.mutate(x.id); }}>
            <span className={`text-sm ${x.read_at ? '' : 'font-semibold'}`}>{x.title}</span>
            <span className="text-xs text-muted-foreground line-clamp-2">{x.body}</span>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild><Link to="/dashboard/notifications" className="justify-center text-sm cursor-pointer">View all</Link></DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
