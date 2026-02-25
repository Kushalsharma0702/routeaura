/**
 * StatusBadge Component
 * 
 * Displays booking/payment status with appropriate colors and icons
 * Each status has a unique color scheme for quick visual identification
 * 
 * Supported statuses:
 * - pending/unpaid: Yellow (warning)
 * - approved/paid: Green (success)
 * - rejected: Red (destructive)
 * - refunded: Gray (muted)
 */
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

type BadgeVariant = 'pending' | 'approved' | 'rejected' | 'paid' | 'unpaid' | 'refunded';

// Color schemes for each status type
const variants: Record<BadgeVariant, string> = {
  pending: 'bg-warning/15 text-warning border-warning/20',
  approved: 'bg-success/15 text-success border-success/20',
  rejected: 'bg-destructive/15 text-destructive border-destructive/20',
  paid: 'bg-success/15 text-success border-success/20',
  unpaid: 'bg-warning/15 text-warning border-warning/20',
  refunded: 'bg-muted text-muted-foreground border-border',
};

export default function StatusBadge({ status }: { status: BadgeVariant }) {
  return (
    <motion.span
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border capitalize', variants[status])}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full mr-1.5', {
        'bg-warning': status === 'pending' || status === 'unpaid',
        'bg-success': status === 'approved' || status === 'paid',
        'bg-destructive': status === 'rejected',
        'bg-muted-foreground': status === 'refunded',
      })} />
      {status}
    </motion.span>
  );
}
