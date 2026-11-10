import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Compass, Eye, EyeOff, AlertCircle, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

const loginSchema = z.object({
  email: z.string().trim().email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});
const registerSchema = z.object({
  full_name: z.string().trim().min(1, 'Your name is required').max(120),
  email: z.string().trim().email('Enter a valid email address'),
  phone: z.string().trim().regex(/^([+0-9()\-\s]{6,32})?$/, 'Enter a valid phone number').optional(),
  password: z.string().min(8, 'At least 8 characters')
    .regex(/[A-Za-z]/, 'Include a letter').regex(/\d/, 'Include a digit'),
});
type FormValues = { full_name?: string; email: string; phone?: string; password: string };

// Development-only quick fill. Values come from .env.development; hidden in production builds.
const DEV_ACCOUNTS = import.meta.env.DEV
  ? {
      admin: { email: import.meta.env.VITE_DEV_ADMIN_EMAIL, password: import.meta.env.VITE_DEV_ADMIN_PASSWORD },
      client: { email: import.meta.env.VITE_DEV_TRAVELER_EMAIL, password: import.meta.env.VITE_DEV_TRAVELER_PASSWORD },
    }
  : null;

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const { login, register: registerUser } = useAuth();
  const navigate = useNavigate();

  const { register, handleSubmit, reset, setValue, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(mode === 'login' ? loginSchema : registerSchema),
  });

  const onSubmit = async (values: FormValues) => {
    setError('');
    const err = mode === 'login'
      ? await login(values.email, values.password)
      : await registerUser({
          email: values.email, password: values.password,
          full_name: values.full_name ?? '', phone: values.phone || undefined,
        });
    if (err) { setError(err); return; }
    navigate('/', { replace: true }); // Index routes to the correct dashboard by role
  };

  const switchMode = (m: 'login' | 'register') => { setMode(m); setError(''); reset(); };

  const fillDemo = (role: 'admin' | 'client') => {
    const acct = DEV_ACCOUNTS?.[role];
    if (!acct?.email || !acct.password) return;
    setMode('login');
    setValue('email', acct.email);
    setValue('password', acct.password);
    setError('');
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Panel */}
      <div className="hidden lg:flex lg:w-1/2 gradient-hero relative overflow-hidden items-center justify-center p-12">
        {/* Background Image */}
        <div className="absolute inset-0">
          <img 
            src="https://images.unsplash.com/photo-1506905925346-21bda4d32df4?q=80&w=2000" 
            alt="Paragliding over mountains" 
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-br from-primary/80 via-primary/70 to-accent/80" />
        </div>
        <div className="absolute inset-0 opacity-10">
          {[...Array(5)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute rounded-full border border-primary-foreground/20"
              style={{
                width: `${180 + i * 140}px`, height: `${180 + i * 140}px`,
                top: '50%', left: '50%',
                transform: 'translate(-50%, -50%)',
              }}
              animate={{ rotate: i % 2 === 0 ? 360 : -360 }}
              transition={{ duration: 25 + i * 8, repeat: Infinity, ease: 'linear' }}
            />
          ))}
        </div>
        <motion.div
          initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9 }}
          className="relative z-10 text-primary-foreground text-center"
        >
          <div className="flex items-center justify-center gap-3 mb-8">
            <div className="w-14 h-14 rounded-2xl bg-primary-foreground/20 backdrop-blur-sm flex items-center justify-center">
              <Compass className="w-7 h-7 text-primary-foreground" />
            </div>
            <h1 className="text-4xl font-display font-bold tracking-tight">RouteAura</h1>
          </div>
          <p className="text-xl opacity-90 max-w-md leading-relaxed">
            Your premium travel management platform. Discover routes, book experiences, and travel with elegance.
          </p>
          <div className="mt-12 grid grid-cols-3 gap-6 text-center">
            {[{ n: '500+', l: 'Destinations' }, { n: '10K+', l: 'Travelers' }, { n: '98%', l: 'Satisfaction' }].map(s => (
              <motion.div key={s.l} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
                <div className="text-2xl font-bold font-display">{s.n}</div>
                <div className="text-sm opacity-75">{s.l}</div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 flex items-center justify-center p-6 bg-background">
        <motion.div
          initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="w-full max-w-md"
        >
          <div className="lg:hidden flex items-center gap-2 mb-8 justify-center">
            <div className="w-10 h-10 rounded-xl gradient-primary flex items-center justify-center">
              <Compass className="w-5 h-5 text-primary-foreground" />
            </div>
            <span className="text-2xl font-display font-bold text-foreground">RouteAura</span>
          </div>

          <Card className="shadow-glass border-border/50 glass-strong">
            <CardHeader className="space-y-1 pb-4">
              <h2 className="text-2xl font-display font-bold text-foreground">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
              <p className="text-muted-foreground text-sm">{mode === 'login' ? 'Sign in to your account to continue' : 'Start planning your next trip'}</p>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
                {error && (
                  <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} role="alert"
                    className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {error}
                  </motion.div>
                )}
                {mode === 'register' && (
                  <div className="space-y-2">
                    <Label htmlFor="full_name">Full name</Label>
                    <Input id="full_name" autoComplete="name" className="h-11" aria-invalid={!!errors.full_name}
                      {...register('full_name')} />
                    {errors.full_name && <p className="text-xs text-destructive">{errors.full_name.message}</p>}
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" type="email" autoComplete="email" placeholder="Enter your email" className="h-11"
                    aria-invalid={!!errors.email} {...register('email')} />
                  {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                </div>
                {mode === 'register' && (
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone (optional)</Label>
                    <Input id="phone" type="tel" autoComplete="tel" className="h-11" aria-invalid={!!errors.phone}
                      {...register('phone')} />
                    {errors.phone && <p className="text-xs text-destructive">{errors.phone.message}</p>}
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <div className="relative">
                    <Input id="password" type={showPassword ? 'text' : 'password'} placeholder="Enter your password"
                      autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                      className="pr-10 h-11" aria-invalid={!!errors.password} {...register('password')} />
                    <button type="button" onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
                </div>
                <Button type="submit" className="w-full h-11 gradient-primary text-primary-foreground font-medium" disabled={isSubmitting}>
                  {isSubmitting ? (
                    <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1 }}>
                      <Sparkles className="w-4 h-4" />
                    </motion.div>
                  ) : mode === 'login' ? 'Sign In' : 'Create Account'}
                </Button>
              </form>

              <p className="mt-4 text-sm text-center text-muted-foreground">
                {mode === 'login' ? 'New to RouteAura?' : 'Already have an account?'}{' '}
                <button type="button" className="text-primary font-medium hover:underline"
                  onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}>
                  {mode === 'login' ? 'Create an account' : 'Sign in'}
                </button>
              </p>

              {DEV_ACCOUNTS && mode === 'login' && (
                <div className="mt-6">
                  <p className="text-xs text-muted-foreground text-center mb-3">Development quick access</p>
                  <div className="grid grid-cols-2 gap-3">
                    <Button type="button" variant="outline" size="sm" onClick={() => fillDemo('admin')} className="text-xs h-9">
                      Admin Demo
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={() => fillDemo('client')} className="text-xs h-9">
                      Client Demo
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
