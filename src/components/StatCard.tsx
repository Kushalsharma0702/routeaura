/**
 * StatCard Component
 * 
 * A reusable card component for displaying statistics and metrics
 * Used in both admin and client dashboards
 * 
 * Features:
 * - Animated entrance and hover effects
 * - Multiple color variants (primary, accent, success, warning)
 * - Optional trend indicator
 * - Responsive sizing
 */
import { motion } from 'framer-motion';
import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatCardProps {
  title: string;  // Label for the stat (e.g., "Total Users")
  value: string | number;  // The actual value to display
  icon: LucideIcon;  // Icon from lucide-react
  trend?: string;  // Optional trend text (e.g., "+12% this month")
  trendUp?: boolean;  // Whether trend is positive (green) or negative (red)
  variant?: 'default' | 'primary' | 'accent' | 'success' | 'warning';  // Color scheme
}

// Icon background colors based on variant
const iconVariants = {
  default: 'bg-muted text-muted-foreground',
  primary: 'gradient-primary text-primary-foreground',
  accent: 'gradient-accent text-accent-foreground',
  success: 'bg-success text-success-foreground',
  warning: 'bg-warning text-warning-foreground',
};

export default function StatCard({ title, value, icon: Icon, trend, trendUp, variant = 'default' }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2, transition: { duration: 0.2 } }}
      className="bg-card rounded-xl border border-border/50 p-4 sm:p-6 shadow-card hover:shadow-card-hover transition-shadow"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs sm:text-sm text-muted-foreground font-medium truncate">{title}</p>
          <p className="text-lg sm:text-2xl font-display font-bold text-card-foreground mt-1">{value}</p>
          {trend && (
            <p className={cn('text-xs mt-1 font-medium', trendUp ? 'text-success' : 'text-destructive')}>
              {trend}
            </p>
          )}
        </div>
        <div className={cn('w-9 h-9 sm:w-11 sm:h-11 rounded-xl flex items-center justify-center shrink-0', iconVariants[variant])}>
          <Icon className="w-4 h-4 sm:w-5 sm:h-5" />
        </div>
      </div>
    </motion.div>
  );
}
