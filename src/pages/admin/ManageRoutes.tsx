import { useState } from 'react';
import { routes as initialRoutes, Route as RouteType } from '@/data/mockData';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Plus, Route, Plane, Car, Train, ArrowRight, MapPin } from 'lucide-react';
import { motion } from 'framer-motion';

const modeIcons = { Flight: Plane, Road: Car, Train: Train };
const modeColors = { Flight: 'bg-primary/10 text-primary', Road: 'bg-success/10 text-success', Train: 'bg-warning/10 text-warning' };

export default function ManageRoutes() {
  const [routes, setRoutes] = useState<RouteType[]>(initialRoutes);
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleSave = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const route: RouteType = {
      id: `rt-${Date.now()}`,
      source: fd.get('source') as string,
      destination: fd.get('destination') as string,
      stops: (fd.get('stops') as string || '').split(',').map(s => s.trim()).filter(Boolean),
      distance: fd.get('distance') as string,
      travelMode: fd.get('mode') as 'Flight' | 'Road' | 'Train',
      duration: fd.get('duration') as string,
    };
    setRoutes(prev => [...prev, route]);
    setDialogOpen(false);
  };

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">Route Mapping</h1>
          <p className="text-sm text-muted-foreground mt-1">{routes.length} travel routes configured</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gradient-primary text-primary-foreground gap-2">
              <Plus className="w-4 h-4" /> Add Route
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-display">Add New Route</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSave} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Source City</Label>
                  <Input name="source" required />
                </div>
                <div className="space-y-2">
                  <Label>Destination</Label>
                  <Input name="destination" required />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label>Stops (comma-separated)</Label>
                  <Input name="stops" placeholder="Dubai, Singapore" />
                </div>
                <div className="space-y-2">
                  <Label>Distance</Label>
                  <Input name="distance" placeholder="8,800 km" required />
                </div>
                <div className="space-y-2">
                  <Label>Duration</Label>
                  <Input name="duration" placeholder="12h" required />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label>Travel Mode</Label>
                  <Select name="mode" defaultValue="Flight">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Flight">Flight</SelectItem>
                      <SelectItem value="Road">Road</SelectItem>
                      <SelectItem value="Train">Train</SelectItem>
                    </SelectContent>
                  </Select>
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

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {routes.map((route, i) => {
          const ModeIcon = modeIcons[route.travelMode];
          return (
            <motion.div key={route.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              whileHover={{ y: -2, transition: { duration: 0.2 } }}
              className="bg-card rounded-xl border border-border/50 shadow-card p-5 space-y-4">
              {/* Route Header */}
              <div className="flex items-center justify-between">
                <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium ${modeColors[route.travelMode]}`}>
                  <ModeIcon className="w-3.5 h-3.5" />
                  {route.travelMode}
                </div>
                <span className="text-xs text-muted-foreground">{route.distance}</span>
              </div>

              {/* Route Visual */}
              <div className="flex items-center gap-3">
                <div className="text-center">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center mb-1">
                    <MapPin className="w-4 h-4 text-primary" />
                  </div>
                  <p className="text-xs font-medium text-card-foreground">{route.source}</p>
                </div>
                <div className="flex-1 flex items-center gap-1">
                  <div className="flex-1 h-px bg-border relative">
                    {route.stops.map((stop, si) => (
                      <div key={si} className="absolute top-1/2 -translate-y-1/2"
                        style={{ left: `${((si + 1) / (route.stops.length + 1)) * 100}%` }}>
                        <div className="w-2 h-2 rounded-full bg-accent -translate-x-1/2" title={stop} />
                      </div>
                    ))}
                  </div>
                  <ArrowRight className="w-4 h-4 text-muted-foreground" />
                </div>
                <div className="text-center">
                  <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center mb-1">
                    <MapPin className="w-4 h-4 text-accent-foreground" />
                  </div>
                  <p className="text-xs font-medium text-card-foreground">{route.destination}</p>
                </div>
              </div>

              {/* Stops */}
              {route.stops.length > 0 && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span>Stops:</span>
                  {route.stops.map((stop, si) => (
                    <span key={si} className="bg-muted px-2 py-0.5 rounded">{stop}</span>
                  ))}
                </div>
              )}

              {/* Duration */}
              <div className="text-xs text-muted-foreground border-t border-border/30 pt-3">
                Estimated duration: <span className="font-medium text-card-foreground">{route.duration}</span>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
