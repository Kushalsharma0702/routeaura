/**
 * Landing Page / Home Route
 * This is the entry point of the app (path: "/")
 * It intelligently redirects users based on their authentication status:
 * - Not logged in → sends to login page
 * - Admin user → sends to admin dashboard
 * - Regular user → sends to client dashboard
 */
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

const Index = () => {
  const { isAuthenticated, user } = useAuth();

  // If user is logged in, send them to their appropriate dashboard
  if (isAuthenticated) {
    return <Navigate to={user?.role === 'admin' ? '/admin' : '/dashboard'} replace />;
  }
  
  // Not logged in? Send to login page
  return <Navigate to="/login" replace />;
};

export default Index;
