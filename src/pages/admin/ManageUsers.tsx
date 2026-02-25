import { demoUsers, bookings } from '@/data/mockData';
import { motion } from 'framer-motion';
import { Mail, Phone, Calendar, BookOpen } from 'lucide-react';

export default function ManageUsers() {
  const clients = demoUsers.filter(u => u.role === 'client');

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Manage Users</h1>
        <p className="text-sm text-muted-foreground mt-1">{clients.length} registered clients</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {clients.map((user, i) => {
          const userBookings = bookings.filter(b => b.clientId === user.id);
          return (
            <motion.div key={user.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              whileHover={{ y: -2, transition: { duration: 0.2 } }}
              className="bg-card rounded-xl border border-border/50 shadow-card p-6 hover:shadow-card-hover transition-shadow">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-12 h-12 rounded-full gradient-primary flex items-center justify-center text-lg font-bold text-primary-foreground">
                  {user.name.charAt(0)}
                </div>
                <div>
                  <h3 className="font-semibold text-card-foreground">{user.name}</h3>
                  <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full capitalize">{user.role}</span>
                </div>
              </div>
              <div className="space-y-2 text-sm text-muted-foreground">
                <div className="flex items-center gap-2"><Mail className="w-4 h-4" />{user.email}</div>
                <div className="flex items-center gap-2"><Phone className="w-4 h-4" />{user.phone}</div>
                <div className="flex items-center gap-2"><Calendar className="w-4 h-4" />Joined {user.joinedDate}</div>
                <div className="flex items-center gap-2"><BookOpen className="w-4 h-4" />{userBookings.length} booking{userBookings.length !== 1 ? 's' : ''}</div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
