import { useState } from 'react';
import { destinations as initialDestinations, Destination } from '@/data/mockData';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Plus, MapPin, Calendar, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';
import ImageGallery from '@/components/ImageGallery';

export default function ManageDestinations() {
  const [dests, setDests] = useState<Destination[]>(initialDestinations);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedDest, setSelectedDest] = useState<Destination | null>(null);

  const handleSave = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const dest: Destination = {
      id: `dest-${Date.now()}`,
      name: fd.get('name') as string,
      country: fd.get('country') as string,
      description: fd.get('description') as string,
      images: (fd.get('images') as string || '').split(',').map(s => s.trim()).filter(Boolean),
      travelSeason: fd.get('season') as string,
      attractions: (fd.get('attractions') as string || '').split(',').map(s => s.trim()).filter(Boolean),
    };
    setDests(prev => [...prev, dest]);
    setDialogOpen(false);
  };

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">Destinations</h1>
          <p className="text-sm text-muted-foreground mt-1">{dests.length} travel destinations</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gradient-primary text-primary-foreground gap-2">
              <Plus className="w-4 h-4" /> Add Destination
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-display">Add New Destination</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSave} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input name="name" required />
                </div>
                <div className="space-y-2">
                  <Label>Country</Label>
                  <Input name="country" required />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label>Description</Label>
                  <Input name="description" required />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label>Image URLs (comma-separated)</Label>
                  <Input name="images" placeholder="https://..., https://..." />
                </div>
                <div className="space-y-2">
                  <Label>Travel Season</Label>
                  <Input name="season" placeholder="Apr - Oct" required />
                </div>
                <div className="space-y-2">
                  <Label>Attractions (comma-separated)</Label>
                  <Input name="attractions" placeholder="Temple, Beach, Mountain" />
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                <Button type="submit" className="gradient-primary text-primary-foreground">Create</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {dests.map((dest, i) => (
          <motion.div key={dest.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            whileHover={{ y: -4, transition: { duration: 0.2 } }}
            className="bg-card rounded-xl border border-border/50 shadow-card overflow-hidden cursor-pointer"
            onClick={() => setSelectedDest(dest)}
          >
            <div className="relative h-48 overflow-hidden">
              <img src={dest.images[0]} alt={dest.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              <div className="absolute inset-0 bg-gradient-to-t from-foreground/70 to-transparent" />
              <div className="absolute bottom-4 left-4 text-primary-foreground">
                <div className="flex items-center gap-1.5 mb-1">
                  <MapPin className="w-4 h-4" />
                  <h3 className="font-display font-semibold text-lg">{dest.name}</h3>
                </div>
                <p className="text-xs opacity-80">{dest.country}</p>
              </div>
            </div>
            <div className="p-4 space-y-2">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Calendar className="w-3.5 h-3.5" />
                <span>Best: {dest.travelSeason}</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {dest.attractions.slice(0, 3).map(a => (
                  <span key={a} className="text-xs bg-accent/10 text-accent-foreground px-2 py-0.5 rounded-full">{a}</span>
                ))}
                {dest.attractions.length > 3 && (
                  <span className="text-xs text-muted-foreground">+{dest.attractions.length - 3} more</span>
                )}
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Destination Detail Dialog */}
      <Dialog open={!!selectedDest} onOpenChange={o => !o && setSelectedDest(null)}>
        <DialogContent className="max-w-lg">
          {selectedDest && (
            <>
              <DialogHeader>
                <DialogTitle className="font-display">{selectedDest.name}, {selectedDest.country}</DialogTitle>
              </DialogHeader>
              <ImageGallery images={selectedDest.images} title={selectedDest.name} />
              <p className="text-sm text-muted-foreground">{selectedDest.description}</p>
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="w-4 h-4 text-primary" />
                <span className="text-card-foreground">Best Season: {selectedDest.travelSeason}</span>
              </div>
              <div>
                <p className="text-sm font-medium text-card-foreground mb-2 flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-primary" /> Top Attractions
                </p>
                <div className="flex flex-wrap gap-2">
                  {selectedDest.attractions.map(a => (
                    <span key={a} className="text-xs bg-primary/10 text-primary px-3 py-1 rounded-full">{a}</span>
                  ))}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
