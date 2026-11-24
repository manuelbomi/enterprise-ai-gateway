// ============================================================
// src/App.tsx — Root Application Component & Router
//
// ARCHITECT'S NOTE:
//   React Router v6 defines the entire navigation tree here.
//   Three route patterns:
//     1. Public routes (/login) — no auth required
//     2. Protected routes (/*) — redirect to /login if not authenticated
//     3. Admin routes (/admin) — redirect if not admin role
// ============================================================

import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';
import { MainLayout } from '@/components/Layout/MainLayout';
import { LoginPage } from '@/pages/Login/LoginPage';
import { ChatPage } from '@/pages/Chat/ChatPage';
import { DashboardPage } from '@/pages/Dashboard/DashboardPage';
import { AdminPage } from '@/pages/Admin/AdminPage';

// React Query client — caches server state globally
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,  // data is fresh for 5 minutes
      retry: 1,                  // retry failed queries once
    },
  },
});

// ---- Protected Route Guard ----
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuthStore();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

// ---- Admin Route Guard ----
const AdminRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'super_admin' || user?.role === 'team_admin';

  if (!isAdmin) {
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
};

// ---- App Shell ----
const AppContent: React.FC = () => {
  const loadUser = useAuthStore((s) => s.loadUser);

  // On mount: validate the stored JWT and load user profile
  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected — requires authentication */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route
          path="admin"
          element={
            <AdminRoute>
              <AdminPage />
            </AdminRoute>
          }
        />
      </Route>

      {/* Catch-all — redirect unknown paths to chat */}
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
};

// ---- Root Export ----
const App: React.FC = () => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  </QueryClientProvider>
);

export default App;
