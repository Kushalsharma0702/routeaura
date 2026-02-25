import { useState } from 'react';
import { travelPackages, TravelPackage, formatINR } from '@/data/mockData';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { Plus, Pencil, Trash2, Search, Eye, EyeOff } from 'lucide-react';
import { motion } from 'framer-motion';
import ImageGallery from '@/components/ImageGallery';

export default function ManagePackages() {
  const [packages, setPackages] = useState<TravelPackage[]>(travelPackages);
  const [search, setSearch] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<TravelPackage | null>(null);

  const filtered = packages.filter(p =>
    p.title.toLowerCase().includes(search.toLowerCase()) ||
    p.destination.toLowerCase().includes(search.toLowerCase()) ||
    p.tags.some(t => t.toLowerCase().includes(search.toLowerCase()))
  );

  const handleDelete = (id: string) => {
    setPackages(prev => prev.filter(p => p.id !== id));
  };

  const toggleVisibility = (id: string) => {
    setPackages(prev => prev.map(p => p.id === id ? { ...p, visible: !p.visible } : p));
  };

  const handleSave = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const pkg: TravelPackage = {
      id: editing?.id || `pkg-${Date.now()}`,
      title: fd.get('title') as string,
      destination: fd.get('destination') as string,
      description: fd.get('description') as string,
      price: Number(fd.get('price')),
      duration: Number(fd.get('duration')),
      availableSeats: Number(fd.get('seats')),
      travelDate: fd.get('travelDate') as string,
      images: (fd.get('images') as string || '').split(',').map(s => s.trim()).filter(Boolean),
      rating: editing?.rating || 4.5,
      category: fd.get('category') as string || 'Beach',
      tags: (fd.get('tags') as string || '').split(',').map(s => s.trim()).filter(Boolean),
      visible: editing?.visible ?? true,
    };
    if (pkg.images.length === 0) {
      pkg.images = ['https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800'];
    }
    if (editing) {
      setPackages(prev => prev.map(p => p.id === editing.id ? pkg : p));
    } else {
      setPackages(prev => [...prev, pkg]);
    }
    setDialogOpen(false);
    setEditing(null);
  };

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">Travel Packages</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage your travel packages</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) setEditing(null); }}>
          <DialogTrigger asChild>
            <Button className="gradient-primary text-primary-foreground gap-2">
              <Plus className="w-4 h-4" /> Add Package
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-display">{editing ? 'Edit Package' : 'Add New Package'}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSave} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2 col-span-2">
                  <Label>Title</Label>
                  <Input name="title" defaultValue={editing?.title} required />
                </div>
                <div className="space-y-2">
                  <Label>Destination</Label>
                  <Input name="destination" defaultValue={editing?.destination} required />
                </div>
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Input name="category" defaultValue={editing?.category} required />
                </div>
                <div className="space-y-2">
                  <Label>Price (₹)</Label>
                  <Input name="price" type="number" defaultValue={editing?.price} required />
                </div>
                <div className="space-y-2">
                  <Label>Duration (days)</Label>
                  <Input name="duration" type="number" defaultValue={editing?.duration} required />
                </div>
                <div className="space-y-2">
                  <Label>Available Seats</Label>
                  <Input name="seats" type="number" defaultValue={editing?.availableSeats} required />
                </div>
                <div className="space-y-2">
                  <Label>Travel Date</Label>
                  <Input name="travelDate" type="date" defaultValue={editing?.travelDate} required />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label>Image URLs (comma-separated)</Label>
                  <Input name="images" defaultValue={editing?.images?.join(', ')} placeholder="https://..., https://..." />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label>Tags (comma-separated)</Label>
                  <Input name="tags" defaultValue={editing?.tags?.join(', ')} placeholder="Adventure, Family, Budget" />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label>Description</Label>
                  <Input name="description" defaultValue={editing?.description} required />
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => { setDialogOpen(false); setEditing(null); }}>Cancel</Button>
                <Button type="submit" className="gradient-primary text-primary-foreground">{editing ? 'Update' : 'Create'}</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input placeholder="Search packages or tags..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {filtered.map((pkg, i) => (
          <motion.div key={pkg.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            whileHover={{ y: -4, transition: { duration: 0.2 } }}
            className={`bg-card rounded-xl border border-border/50 shadow-card overflow-hidden transition-shadow ${!pkg.visible ? 'opacity-60' : ''}`}>
            <div className="h-40 overflow-hidden relative">
              <img src={pkg.images[0]} alt={pkg.title} className="w-full h-full object-cover" />
              {!pkg.visible && (
                <div className="absolute inset-0 bg-foreground/40 flex items-center justify-center">
                  <span className="text-primary-foreground text-sm font-medium bg-foreground/60 px-3 py-1 rounded-full">Hidden</span>
                </div>
              )}
            </div>
            <div className="p-4 sm:p-5 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-card-foreground text-sm sm:text-base">{pkg.title}</h3>
                  <p className="text-xs text-muted-foreground">{pkg.destination}</p>
                </div>
                <span className="text-base sm:text-lg font-display font-bold text-primary">{formatINR(pkg.price)}</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {pkg.tags.map(tag => (
                  <span key={tag} className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full">{tag}</span>
                ))}
              </div>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span>{pkg.duration} days</span>
                <span>{pkg.availableSeats} seats</span>
                <span>⭐ {pkg.rating}</span>
              </div>
              <div className="flex gap-2 pt-2">
                <Button size="sm" variant="outline" className="flex-1 gap-1"
                  onClick={() => { setEditing(pkg); setDialogOpen(true); }}>
                  <Pencil className="w-3 h-3" /> Edit
                </Button>
                <Button size="sm" variant="outline" onClick={() => toggleVisibility(pkg.id)}
                  className="gap-1">
                  {pkg.visible ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                </Button>
                <Button size="sm" variant="outline" className="text-destructive hover:bg-destructive/10"
                  onClick={() => handleDelete(pkg.id)}>
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
