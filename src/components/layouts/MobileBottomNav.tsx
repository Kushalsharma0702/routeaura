import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard, Package, BookOpen, Users, MapPin, Route,
  Globe, CalendarDays, User,
} from 'lucide-react';
import { motion } from 'framer-motion';

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

const adminNav: NavItem[] = [
  { label: 'Home', href: '/admin', icon: LayoutDashboard },
  { label: 'Packages', href: '/admin/packages', icon: Package },
  { label: 'Bookings', href: '/admin/bookings', icon: BookOpen },
  { label: 'Users', href: '/admin/users', icon: Users },
  { label: 'More', href: '/admin/destinations', icon: MapPin },
];

const clientNav: NavItem[] = [
  { label: 'Home', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Explore', href: '/dashboard/packages', icon: Globe },
  { label: 'Bookings', href: '/dashboard/bookings', icon: CalendarDays },
  { label: 'Profile', href: '/dashboard/profile', icon: User },
];

export default function MobileBottomNav() {
  const { user } = useAuth();
  const location = useLocation();
  const navItems = user?.role === 'admin' ? adminNav : clientNav;

  const isActive = (href: string) => {
    if (href === '/admin' || href === '/dashboard') return location.pathname === href;
    return location.pathname.startsWith(href);
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 lg:hidden">
      <motion.nav
        initial={{ y: 80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: 'spring', damping: 20, stiffness: 180 }}
        className="flex items-center gap-1 px-3 py-2 rounded-full bg-card/80 backdrop-blur-2xl border border-border/40 shadow-glass"
      >
        {navItems.map(item => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                'relative flex flex-col items-center gap-0.5 px-3.5 py-1.5 rounded-full transition-all duration-200',
                active
                  ? 'text-primary-foreground'
                  : 'text-muted-foreground'
              )}
            >
              {active && (
                <motion.div
                  layoutId="mobile-nav-pill"
                  className="absolute inset-0 rounded-full gradient-primary shadow-md"
                  transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                />
              )}
              <item.icon className="w-5 h-5 relative z-10" />
              <span className="text-[10px] font-medium relative z-10 leading-none">{item.label}</span>
            </Link>
          );
        })}
      </motion.nav>
    </div>
  );
}
