import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Compass, Eye, EyeOff, AlertCircle, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    const success = await login(email, password);
    setLoading(false);
    if (success) {
      const user = JSON.parse(localStorage.getItem('routeaura_user') || '{}');
      navigate(user.role === 'admin' ? '/admin' : '/dashboard');
    } else {
      setError('Invalid email or password');
    }
  };

  const fillDemo = (role: 'admin' | 'client') => {
    if (role === 'admin') {
      setEmail('admin@routeaura.com');
      setPassword('Admin@123');
    } else {
      setEmail('client@routeaura.com');
      setPassword('Client@123');
    }
    setError('');
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Panel */}
      <div className="hidden lg:flex lg:w-1/2 gradient-hero relative overflow-hidden items-center justify-center p-12">
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
              <h2 className="text-2xl font-display font-bold text-foreground">Welcome back</h2>
              <p className="text-muted-foreground text-sm">Sign in to your account to continue</p>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {error}
                  </motion.div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" type="email" placeholder="Enter your email" value={email}
                    onChange={e => setEmail(e.target.value)} required className="h-11" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <div className="relative">
                    <Input id="password" type={showPassword ? 'text' : 'password'} placeholder="Enter your password"
                      value={password} onChange={e => setPassword(e.target.value)} required className="pr-10 h-11" />
                    <button type="button" onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
                <Button type="submit" className="w-full h-11 gradient-primary text-primary-foreground font-medium" disabled={loading}>
                  {loading ? (
                    <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1 }}>
                      <Sparkles className="w-4 h-4" />
                    </motion.div>
                  ) : 'Sign In'}
                </Button>
              </form>

              <div className="mt-6">
                <p className="text-xs text-muted-foreground text-center mb-3">Quick demo access</p>
                <div className="grid grid-cols-2 gap-3">
                  <Button variant="outline" size="sm" onClick={() => fillDemo('admin')} className="text-xs h-9">
                    Admin Demo
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => fillDemo('client')} className="text-xs h-9">
                    Client Demo
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
