// Core UI Components - These handle notifications and tooltips throughout the app
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

// React Query for data fetching and caching
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// React Router for navigation
import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

// Authentication context for managing user login/logout
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ApiError } from "@/lib/api/client";

// Page Components
const Index = lazy(() => import("./pages/Index"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Login = lazy(() => import("./pages/Login"));

// Layout wrapper for dashboard pages
import DashboardLayout from "./components/layouts/DashboardLayout";

// Admin Pages - Only accessible to admin users
const AdminDashboard = lazy(() => import("./pages/admin/AdminDashboard"));
const ManageBookings = lazy(() => import("./pages/admin/ManageBookings"));
const ManageUsers = lazy(() => import("./pages/admin/ManageUsers"));
const ManageDestinations = lazy(() => import("./pages/admin/ManageDestinations"));

// Client Pages - Accessible to regular users
const ClientDashboard = lazy(() => import("./pages/client/ClientDashboard"));
const MyBookings = lazy(() => import("./pages/client/MyBookings"));
const ClientProfile = lazy(() => import("./pages/client/ClientProfile"));
const ManageAttractions = lazy(() => import("./pages/admin/ManageAttractions"));
const Planner = lazy(() => import("./pages/client/Planner"));
const Itineraries = lazy(() => import("./pages/client/Itineraries"));
const ItineraryDetail = lazy(() => import("./pages/client/ItineraryDetail"));
const Hotels = lazy(() => import("./pages/client/Hotels"));
const HotelDetail = lazy(() => import("./pages/client/HotelDetail"));
const Notifications = lazy(() => import("./pages/client/Notifications"));
const Assistant = lazy(() => import("./pages/client/Assistant"));
const ManageHotels = lazy(() => import("./pages/admin/ManageHotels"));
const Recommendations = lazy(() => import("./pages/client/Recommendations"));
const BrowseDestinations = lazy(() => import("./pages/client/BrowseDestinations"));
const DestinationDetail = lazy(() => import("./pages/client/DestinationDetail"));

/**
 * Initialize React Query client with optimized caching configuration
 * - Cache data for 5 minutes (staleTime)
 * - Keep unused data in cache for 10 minutes (gcTime)
 * - Retry failed requests twice
 * - Refetch on window focus for fresh data
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes - data considered fresh
      gcTime: 10 * 60 * 1000, // 10 minutes - garbage collection time
      // Retry transient failures only; 4xx responses (validation, auth, not found) will not change on retry
      retry: (count: number, error: unknown) => !(error instanceof ApiError && error.status < 500) && count < 2,
      refetchOnWindowFocus: true, // Refetch when user returns to tab
      refetchOnReconnect: true, // Refetch when internet reconnects
      refetchOnMount: true, // Refetch when component mounts
    },
  },
});

/**
 * ProtectedRoute Component
 * Wraps routes that require authentication and specific user roles
 * Redirects unauthenticated users to login page
 * Redirects users without proper role to home page
 */
function FullPageSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center" role="status" aria-label="Loading">
      <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
    </div>
  );
}

function ProtectedRoute({ children, role }: { children: React.ReactNode; role: 'admin' | 'client' }) {
  const { isAuthenticated, user, isLoading } = useAuth();

  // Wait for the session restore (refresh cookie) before deciding
  if (isLoading) return <FullPageSpinner />;

  // If user is not logged in, send them to login page
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  
  // If user doesn't have the required role, redirect to home
  if (user?.role !== role) return <Navigate to="/" replace />;
  
  // User is authenticated and has the right role - show the page
  return <DashboardLayout>{children}</DashboardLayout>;
}

/**
 * Main routing configuration
 * Organizes all application routes with proper authentication
 */
const AppRoutes = () => (
  <Routes>
    {/* Public Routes - Anyone can access these */}
    <Route path="/" element={<Index />} />
    <Route path="/login" element={<Login />} />
    
    {/* Admin Routes - Only accessible by admin users */}
    <Route path="/admin" element={<ProtectedRoute role="admin"><AdminDashboard /></ProtectedRoute>} />
    <Route path="/admin/hotels" element={<ProtectedRoute role="admin"><ManageHotels /></ProtectedRoute>} />
    <Route path="/admin/bookings" element={<ProtectedRoute role="admin"><ManageBookings /></ProtectedRoute>} />
    <Route path="/admin/users" element={<ProtectedRoute role="admin"><ManageUsers /></ProtectedRoute>} />
    <Route path="/admin/destinations" element={<ProtectedRoute role="admin"><ManageDestinations /></ProtectedRoute>} />
    <Route path="/admin/destinations/:id/attractions" element={<ProtectedRoute role="admin"><ManageAttractions /></ProtectedRoute>} />

    {/* Client Routes - Accessible by regular logged-in users */}
    <Route path="/dashboard" element={<ProtectedRoute role="client"><ClientDashboard /></ProtectedRoute>} />
    <Route path="/dashboard/planner" element={<ProtectedRoute role="client"><Planner /></ProtectedRoute>} />
    <Route path="/dashboard/itineraries" element={<ProtectedRoute role="client"><Itineraries /></ProtectedRoute>} />
    <Route path="/dashboard/itineraries/:id" element={<ProtectedRoute role="client"><ItineraryDetail /></ProtectedRoute>} />
    <Route path="/dashboard/hotels" element={<ProtectedRoute role="client"><Hotels /></ProtectedRoute>} />
    <Route path="/dashboard/hotels/:ref" element={<ProtectedRoute role="client"><HotelDetail /></ProtectedRoute>} />
    <Route path="/dashboard/notifications" element={<ProtectedRoute role="client"><Notifications /></ProtectedRoute>} />
    <Route path="/dashboard/assistant" element={<ProtectedRoute role="client"><Assistant /></ProtectedRoute>} />
    <Route path="/dashboard/recommendations" element={<ProtectedRoute role="client"><Recommendations /></ProtectedRoute>} />
    <Route path="/dashboard/destinations" element={<ProtectedRoute role="client"><BrowseDestinations /></ProtectedRoute>} />
    <Route path="/dashboard/destinations/:ref" element={<ProtectedRoute role="client"><DestinationDetail /></ProtectedRoute>} />
    <Route path="/dashboard/bookings" element={<ProtectedRoute role="client"><MyBookings /></ProtectedRoute>} />
    <Route path="/dashboard/profile" element={<ProtectedRoute role="client"><ClientProfile /></ProtectedRoute>} />

    {/* 404 - Catch all unmatched routes */}
    <Route path="*" element={<NotFound />} />
  </Routes>
);

/**
 * Main App Component
 * Sets up all necessary providers and wrappers for the application
 * 
 * Provider hierarchy (outer to inner):
 * 1. QueryClientProvider - Manages server state and caching
 * 2. TooltipProvider - Enables tooltips across the app
 * 3. Toaster/Sonner - Toast notification systems
 * 4. BrowserRouter - Enables client-side routing
 * 5. AuthProvider - Manages user authentication state
 */
const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      {/* Toast notifications for user feedback */}
      <Toaster />
      <Sonner />
      
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<FullPageSpinner />}>
            <AppRoutes />
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
