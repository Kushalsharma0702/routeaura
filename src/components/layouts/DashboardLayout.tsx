/**
 * DashboardLayout Component
 * 
 * Main layout wrapper for all dashboard pages (both admin and client)
 * 
 * Features:
 * - Responsive sidebar (desktop) and bottom nav (mobile)
 * - Role-based navigation (different menus for admin vs client)
 * - User profile dropdown
 * - Active link highlighting
 * - Smooth animations and transitions
 */
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Compass, LayoutDashboard, Package, BookOpen, Users, MapPin, Menu, X,
  LogOut, User, ChevronDown, Globe, CalendarDays, Search, Bell, Route,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import MobileBottomNav from './MobileBottomNav';

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

// Navigation items for admin users
const adminNav: NavItem[] = [
  { label: 'Dashboard', href: '/admin', icon: LayoutDashboard },
  { label: 'Packages', href: '/admin/packages', icon: Package },
  { label: 'Bookings', href: '/admin/bookings', icon: BookOpen },
  { label: 'Users', href: '/admin/users', icon: Users },
  { label: 'Destinations', href: '/admin/destinations', icon: MapPin },
  { label: 'Routes', href: '/admin/routes', icon: Route },
];

// Navigation items for regular users
const clientNav: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Browse Packages', href: '/dashboard/packages', icon: Globe },
  { label: 'My Bookings', href: '/dashboard/bookings', icon: CalendarDays },
  { label: 'Profile', href: '/dashboard/profile', icon: User },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Choose navigation items based on user role
  const navItems = user?.role === 'admin' ? adminNav : clientNav;

  // Handle user logout and redirect to login page
  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Check if a navigation link is currently active
  const isActive = (href: string) => {
    if (href === '/admin' || href === '/dashboard') return location.pathname === href;
    return location.pathname.startsWith(href);
  };

  return (
    <div className="min-h-screen flex bg-background">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:w-64 flex-col gradient-sidebar fixed inset-y-0 left-0 z-30">
        <div className="p-6">
          <Link to={user?.role === 'admin' ? '/admin' : '/dashboard'} className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl gradient-accent flex items-center justify-center">
              <Compass className="w-5 h-5 text-accent-foreground" />
            </div>
            <span className="text-lg font-display font-bold text-sidebar-foreground">RouteAura</span>
          </Link>
        </div>

        <nav className="flex-1 px-3 space-y-1">
          {navItems.map(item => (
            <Link
              key={item.href} to={item.href}
              className={cn(
                'flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
                isActive(item.href)
                  ? 'bg-sidebar-primary text-sidebar-primary-foreground shadow-md'
                  : 'text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent'
              )}
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-sidebar-border">
          <div className="flex items-center gap-3 px-2">
            <div className="w-9 h-9 rounded-full gradient-primary flex items-center justify-center text-sm font-semibold text-primary-foreground">
              {user?.name?.charAt(0)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-sidebar-foreground truncate">{user?.name}</p>
              <p className="text-xs text-sidebar-muted truncate capitalize">{user?.role}</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 lg:ml-64 flex flex-col min-h-screen">
        {/* Top Navbar */}
        <header className="sticky top-0 z-20 glass border-b border-border/50">
          <div className="flex items-center justify-between h-14 sm:h-16 px-4 lg:px-8">
            <div className="flex items-center gap-3">
              {/* Mobile logo */}
              <Link to={user?.role === 'admin' ? '/admin' : '/dashboard'} className="flex lg:hidden items-center gap-2">
                <div className="w-8 h-8 rounded-lg gradient-accent flex items-center justify-center">
                  <Compass className="w-4 h-4 text-accent-foreground" />
                </div>
                <span className="text-base font-display font-bold text-foreground">RouteAura</span>
              </Link>
              <div className="hidden sm:flex items-center gap-2 bg-muted rounded-lg px-3 py-2">
                <Search className="w-4 h-4 text-muted-foreground" />
                <input
                  type="text" placeholder="Search..."
                  className="bg-transparent border-none outline-none text-sm text-foreground placeholder:text-muted-foreground w-48"
                />
              </div>
            </div>
            <div className="flex items-center gap-2 sm:gap-3">
              <Button variant="ghost" size="icon" className="relative w-9 h-9">
                <Bell className="w-5 h-5 text-muted-foreground" />
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-accent rounded-full" />
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="gap-2 px-2 sm:px-3">
                    <div className="w-8 h-8 rounded-full gradient-primary flex items-center justify-center text-sm font-semibold text-primary-foreground">
                      {user?.name?.charAt(0)}
                    </div>
                    <span className="hidden sm:inline text-sm font-medium">{user?.name}</span>
                    <ChevronDown className="w-4 h-4 text-muted-foreground hidden sm:block" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem className="text-xs text-muted-foreground">{user?.email}</DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="text-destructive">
                    <LogOut className="w-4 h-4 mr-2" />Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-4 lg:p-8">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {children}
          </motion.div>
        </main>
      </div>

      {/* Mobile Bottom Pill Nav */}
      <MobileBottomNav />
    </div>
  );
}
