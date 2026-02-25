import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { motion } from 'framer-motion';

export default function ClientProfile() {
  const { user } = useAuth();

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    toast.success('Profile updated successfully');
  };

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="max-w-2xl space-y-6 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your account information</p>
      </div>

      <Card className="shadow-card border-border/50">
        <CardHeader>
          <CardTitle className="text-lg font-display">Personal Information</CardTitle>
        </CardHeader>
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
                <Label>Full Name</Label>
                <Input defaultValue={user?.name} />
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input type="email" defaultValue={user?.email} />
              </div>
              <div className="space-y-2">
                <Label>Phone</Label>
                <Input defaultValue={user?.phone} />
              </div>
              <div className="space-y-2">
                <Label>Member Since</Label>
                <Input value={user?.joinedDate} disabled />
              </div>
            </div>
            <Button type="submit" className="gradient-primary text-primary-foreground">Save Changes</Button>
          </form>
        </CardContent>
      </Card>
    </motion.div>
  );
}
