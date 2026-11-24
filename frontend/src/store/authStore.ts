// ============================================================
// src/store/authStore.ts — Auth State (Zustand)
//
// ARCHITECT'S NOTE:
//   Zustand is a lightweight state management library.
//   Unlike Redux, it requires no boilerplate — just define
//   state and actions in a single store function.
//
//   Auth state is global — the user's identity and tokens
//   need to be accessible everywhere (layout, chat, admin).
//   localStorage persists tokens across page refreshes.
// ============================================================

import { create } from 'zustand';
import { User, AuthTokens } from '@/types';
import { authApi } from '@/services/api';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (email: string, password: string) => {
    const tokens: AuthTokens = await authApi.login(email, password);

    // Persist tokens to localStorage
    localStorage.setItem('access_token', tokens.access_token);
    localStorage.setItem('refresh_token', tokens.refresh_token);

    // Load the user profile
    const user = await authApi.me();
    set({ user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null, isAuthenticated: false });
    window.location.href = '/login';
  },

  loadUser: async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      set({ isLoading: false });
      return;
    }
    try {
      const user = await authApi.me();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      // Token is invalid or expired — clear and redirect to login
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
