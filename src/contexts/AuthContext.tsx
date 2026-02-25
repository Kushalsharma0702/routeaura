/**
 * Authentication Context
 * Manages user login state and provides authentication methods throughout the app
 * 
 * Demo Credentials:
 * Admin: admin@routeaura.com / Admin@123
 * Client: client@routeaura.com / Client@123
 */
import React, { createContext, useContext, useState, useCallback } from 'react';
import { User, demoUsers } from '@/data/mockData';

// Type definition for authentication context
interface AuthContextType {
  user: User | null;  // Currently logged-in user (null if not logged in)
  login: (email: string, password: string) => Promise<boolean>;  // Login function
  logout: () => void;  // Logout function
  isAuthenticated: boolean;  // Quick check if user is logged in
}

const AuthContext = createContext<AuthContextType | null>(null);

// Demo credentials for testing the application
// In a real app, this would be handled by a backend API
const DEMO_CREDENTIALS: Record<string, string> = {
  'admin@routeaura.com': 'Admin@123',
  'client@routeaura.com': 'Client@123',
};

/**
 * AuthProvider Component
 * Wraps the app and provides authentication state to all child components
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Initialize user state from localStorage (persists across page refreshes)
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('routeaura_user');
    return saved ? JSON.parse(saved) : null;
  });

  /**
   * Login function - validates credentials and updates state
   * In production, this would call an API endpoint
   */
  const login = useCallback(async (email: string, password: string) => {
    // Check if credentials match our demo credentials
    if (DEMO_CREDENTIALS[email] && DEMO_CREDENTIALS[email] === password) {
      const foundUser = demoUsers.find(u => u.email === email);
      if (foundUser) {
        setUser(foundUser);
        // Save to localStorage so user stays logged in after refresh
        localStorage.setItem('routeaura_user', JSON.stringify(foundUser));
        return true;
      }
    }
    return false;  // Login failed
  }, []);

  /**
   * Logout function - clears user state and localStorage
   */
  const logout = useCallback(() => {
    setUser(null);
    localStorage.removeItem('routeaura_user');
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * useAuth Hook
 * Custom hook to access authentication context in any component
 * Must be used within AuthProvider
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
