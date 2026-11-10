import { useEffect, useState } from 'react';
import { useAuth, toAuthUser } from '@/contexts/AuthContext';
import { ApiError } from '@/lib/api/client';
import { usersApi, type Preferences } from '@/lib/api/users';
import { usePreferences, useSavePreferences } from '@/hooks/useUsers';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import { motion } from 'framer-motion';

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Please try again.');

function PersonalInfo() {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user?.name ?? '');
  const [phone, setPhone] = useState(user?.phone ?? '');
  const [saving, setSaving] = useState(false);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await usersApi.updateMe({ full_name: name, phone: phone || null });
      setUser(toAuthUser(updated));
      toast.success('Profile updated successfully');
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="shadow-card border-border/50">
      <CardHeader><CardTitle className="text-lg font-display">Personal Information</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={handleSave} className="space-y-4">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-full gradient-primary flex items-center justify-center text-2xl font-bold text-primary-foreground">
              {user?.name?.charAt(0)}
            </div>
            <div>
              <h3 className="font-semibold text-card-foreground">{user?.name}</h3>
              <p className="text-sm text-muted-foreground capitalize">{user?.role}</p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="p-name">Full Name</Label>
              <Input id="p-name" value={name} onChange={e => setName(e.target.value)} required maxLength={120} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-email">Email</Label>
              <Input id="p-email" type="email" value={user?.email ?? ''} disabled />
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-phone">Phone</Label>
              <Input id="p-phone" value={phone} onChange={e => setPhone(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-since">Member Since</Label>
              <Input id="p-since" value={user?.joinedDate ?? ''} disabled />
            </div>
          </div>
          <Button type="submit" disabled={saving} className="gradient-primary text-primary-foreground">
            {saving ? 'Saving…' : 'Save Changes'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

const CLIMATES = ['any', 'tropical', 'temperate', 'cold', 'arid'];
const SEASONS = ['any', 'winter', 'summer', 'monsoon', 'spring', 'autumn'];
const STYLES = ['budget', 'comfort', 'luxury', 'adventure', 'relaxed'];
const STAYS = ['hotel', 'hostel', 'resort', 'homestay'];
const LANGS: [string, string][] = [['en', 'English'], ['hi', 'हिन्दी']];

function PreferencesCard() {
  const { data, isLoading, isError, refetch } = usePreferences();
  const save = useSavePreferences();
  const [form, setForm] = useState<Preferences | null>(null);
  const [interests, setInterests] = useState('');
  const [budgetRupees, setBudgetRupees] = useState('');

  useEffect(() => {
    if (data) {
      setForm(data);
      setInterests(data.interests.join(', '));
      setBudgetRupees(data.budget_per_day_minor != null ? String(data.budget_per_day_minor / 100) : '');
    }
  }, [data]);

  if (isLoading) return <Skeleton className="h-64 w-full rounded-xl" />;
  if (isError || !form) {
    return (
      <Card className="shadow-card border-border/50"><CardContent className="p-6 text-sm">
        Could not load your preferences. <Button variant="link" onClick={() => refetch()}>Retry</Button>
      </CardContent></Card>
    );
  }

  const set = <K extends keyof Preferences>(k: K, v: Preferences[K]) => setForm({ ...form, [k]: v });
  const num = (v: string) => (v === '' ? null : Number(v));

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const rupees = num(budgetRupees);
    save.mutate(
      {
        ...form,
        budget_per_day_minor: rupees == null ? null : Math.round(rupees * 100),
        interests: interests.split(',').map(s => s.trim()).filter(Boolean),
      },
      { onSuccess: () => toast.success('Travel preferences saved'), onError: e2 => toast.error(errMsg(e2)) },
    );
  };

  const pick = (label: string, id: string, value: string | null, opts: string[] | [string, string][], key: keyof Preferences) => (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value ?? undefined} onValueChange={v => set(key, v as never)}>
        <SelectTrigger id={id}><SelectValue placeholder="Select" /></SelectTrigger>
        <SelectContent>
          {opts.map(o => {
            const [v, l] = Array.isArray(o) ? o : [o, o];
            return <SelectItem key={v} value={v} className="capitalize">{l}</SelectItem>;
          })}
        </SelectContent>
      </Select>
    </div>
  );

  return (
    <Card className="shadow-card border-border/50">
      <CardHeader><CardTitle className="text-lg font-display">Travel Preferences</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="pr-budget">Budget per day (₹)</Label>
              <Input id="pr-budget" type="number" min={0} value={budgetRupees} onChange={e => setBudgetRupees(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pr-days">Typical trip length (days)</Label>
              <Input id="pr-days" type="number" min={1} max={60} value={form.trip_duration_days ?? ''}
                onChange={e => set('trip_duration_days', num(e.target.value))} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pr-group">Group size</Label>
              <Input id="pr-group" type="number" min={1} max={50} value={form.group_size ?? ''}
                onChange={e => set('group_size', num(e.target.value))} />
            </div>
            {pick('Language', 'pr-lang', form.language, LANGS, 'language')}
            {pick('Preferred climate', 'pr-climate', form.preferred_climate, CLIMATES, 'preferred_climate')}
            {pick('Preferred season', 'pr-season', form.preferred_season, SEASONS, 'preferred_season')}
            {pick('Travel style', 'pr-style', form.travel_style, STYLES, 'travel_style')}
            {pick('Accommodation', 'pr-stay', form.accommodation_preference, STAYS, 'accommodation_preference')}
          </div>
          <div className="space-y-2">
            <Label htmlFor="pr-interests">Interests (comma separated)</Label>
            <Input id="pr-interests" value={interests} placeholder="history, food, adventure"
              onChange={e => setInterests(e.target.value)} />
          </div>
          <Button type="submit" disabled={save.isPending} className="gradient-primary text-primary-foreground">
            {save.isPending ? 'Saving…' : 'Save Preferences'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export default function ClientProfile() {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="max-w-2xl space-y-6 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your account and travel preferences</p>
      </div>
      <PersonalInfo />
      <PreferencesCard />
    </motion.div>
  );
}
