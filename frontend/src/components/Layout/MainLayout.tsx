// ============================================================
// src/components/Layout/MainLayout.tsx — App Shell
// ============================================================

import React from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import {
  MessageSquare, LayoutDashboard, Settings, LogOut, Users, BrainCircuit
} from 'lucide-react';

export const MainLayout: React.FC = () => {
  const { user, logout } = useAuthStore();
  const isSuperAdmin = user?.role === 'super_admin';
  const isAdmin = isSuperAdmin || user?.role === 'team_admin';

  return (
    <div className="flex h-screen bg-gray-100 font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        {/* Brand */}
        <div className="px-6 py-5 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <BrainCircuit className="w-7 h-7 text-brand-400" />
            <div>
              <p className="font-bold text-sm">AI Gateway</p>
              <p className="text-xs text-gray-400">Enterprise Platform</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          <NavItem to="/chat" icon={<MessageSquare className="w-4 h-4" />} label="Chat" />
          <NavItem to="/dashboard" icon={<LayoutDashboard className="w-4 h-4" />} label="Dashboard" />
          {isAdmin && (
            <NavItem to="/admin" icon={<Users className="w-4 h-4" />} label="Admin Panel" />
          )}
        </nav>

        {/* User profile + logout */}
        <div className="px-4 py-4 border-t border-gray-700">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-xs font-bold">
              {user?.full_name?.[0]?.toUpperCase() ?? 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.full_name}</p>
              <p className="text-xs text-gray-400 truncate capitalize">{user?.role?.replace('_', ' ')}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 text-gray-400 hover:text-white text-xs w-full py-1.5 px-2 rounded hover:bg-gray-700 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content area */}
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
};

// ---- NavItem sub-component ----
interface NavItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
}

const NavItem: React.FC<NavItemProps> = ({ to, icon, label }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
        isActive
          ? 'bg-brand-600 text-white'
          : 'text-gray-400 hover:text-white hover:bg-gray-800'
      }`
    }
  >
    {icon}
    {label}
  </NavLink>
);
