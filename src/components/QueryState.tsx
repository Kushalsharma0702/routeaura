import { AlertCircle, SearchX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

export function GridSkeleton({ count = 6, height = 'h-72' }: { count?: number; height?: string }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" role="status" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => <Skeleton key={i} className={`${height} rounded-xl`} />)}
    </div>
  );
}

export function ErrorState({ message = 'Something went wrong while loading this data.', onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center space-y-3">
      <AlertCircle className="w-8 h-8 text-destructive mx-auto" />
      <p className="text-sm text-foreground">{message}</p>
      {onRetry && <Button variant="outline" size="sm" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border p-10 text-center space-y-2">
      <SearchX className="w-8 h-8 text-muted-foreground mx-auto" />
      <p className="font-medium text-foreground">{title}</p>
      {hint && <p className="text-sm text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  return (
    <nav className="flex items-center justify-center gap-3 pt-2" aria-label="Pagination">
      <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
      <span className="text-sm text-muted-foreground" aria-live="polite">Page {page} of {pages}</span>
      <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button>
    </nav>
  );
}
