import { useState } from 'react';
import { Pencil, Trash2, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ApiError } from '@/lib/api/client';
import { useCategories, useDeleteCategory, useSaveCategory } from '@/hooks/useCatalog';

const msg = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong');

export default function CategoriesDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { data, isLoading, isError } = useCategories();
  const save = useSaveCategory();
  const del = useDeleteCategory();
  const [name, setName] = useState('');
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null);

  const add = (e: React.FormEvent) => {
    e.preventDefault();
    save.mutate({ data: { name: name.trim() } }, {
      onSuccess: () => { toast.success('Category created'); setName(''); }, onError: x => toast.error(msg(x)),
    });
  };
  const rename = () => editing && save.mutate({ id: editing.id, data: { name: editing.name.trim() } }, {
    onSuccess: () => { toast.success('Category renamed'); setEditing(null); }, onError: x => toast.error(msg(x)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display">Categories</DialogTitle>
          <DialogDescription>Used to classify destinations and attractions. A category in use cannot be deleted.</DialogDescription>
        </DialogHeader>
        <form onSubmit={add} className="flex gap-2">
          <Input aria-label="New category name" placeholder="New category" value={name} onChange={e => setName(e.target.value)} minLength={2} maxLength={80} required />
          <Button type="submit" disabled={save.isPending} className="gradient-primary text-primary-foreground">Add</Button>
        </form>
        {isLoading && <p className="text-sm text-muted-foreground" role="status">Loading…</p>}
        {isError && <p className="text-sm text-destructive" role="alert">Could not load categories.</p>}
        {data?.length === 0 && <p className="text-sm text-muted-foreground">No categories yet.</p>}
        <ul className="space-y-2 max-h-72 overflow-y-auto">
          {data?.map(c => (
            <li key={c.id} className="flex items-center gap-2 rounded-lg border border-border/50 px-3 py-2">
              {editing?.id === c.id ? (
                <>
                  <Input aria-label={`Rename ${c.name}`} value={editing.name} onChange={e => setEditing({ id: c.id, name: e.target.value })} className="h-8" />
                  <Button size="icon" variant="ghost" aria-label="Save name" onClick={rename}><Check className="w-4 h-4" /></Button>
                  <Button size="icon" variant="ghost" aria-label="Cancel rename" onClick={() => setEditing(null)}><X className="w-4 h-4" /></Button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-sm">{c.name}</span>
                  <Button size="icon" variant="ghost" aria-label={`Rename ${c.name}`} onClick={() => setEditing({ id: c.id, name: c.name })}><Pencil className="w-4 h-4" /></Button>
                  <Button size="icon" variant="ghost" aria-label={`Delete ${c.name}`} disabled={del.isPending}
                    onClick={() => del.mutate(c.id, { onSuccess: () => toast.success('Category deleted'), onError: x => toast.error(msg(x)) })}>
                    <Trash2 className="w-4 h-4 text-destructive" />
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
