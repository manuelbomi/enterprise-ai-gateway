// ============================================================
// src/services/api.ts — Axios HTTP Client & API Layer
//
// ARCHITECT'S NOTE:
//   This module is the single point of contact between the UI and backend.
//   All fetch logic lives here — components never call fetch() directly.
//
//   Key design decisions:
//     1. Axios interceptors auto-attach the JWT token to every request
//     2. The 401 interceptor auto-refreshes the token and retries the request
//        (transparent to the calling component)
//     3. All endpoints are typed functions — no raw axios calls scattered in components
// ============================================================

import axios, {
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import { AuthTokens, User, ChatMessage, ChatResponse, ChatSession, ChatSessionDetail, UsageSummary, DailyCost, Team } from '@/types';

// -------------------------------------------------------
// Axios instance — shared base URL and config
// -------------------------------------------------------

const BASE_URL = import.meta.env.VITE_API_URL || '/api';

const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,   // 30 second timeout for regular calls
});


// -------------------------------------------------------
// Request Interceptor — attach JWT token
// -------------------------------------------------------

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);


// -------------------------------------------------------
// Response Interceptor — handle 401 (token expired)
// -------------------------------------------------------

let isRefreshing = false;
let failedQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token!);
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const originalRequest = error.config;

    // If 401 and we haven't already retried this request
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Queue this request until the token refresh completes
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        // No refresh token — force logout
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const response = await axios.post(`${BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        const { access_token, refresh_token: newRefresh } = response.data;

        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', newRefresh);

        processQueue(null, access_token);
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);


// -------------------------------------------------------
// Auth API
// -------------------------------------------------------

export const authApi = {
  login: async (email: string, password: string): Promise<AuthTokens> => {
    const response = await apiClient.post<AuthTokens>('/auth/login', { email, password });
    return response.data;
  },

  me: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  },

  register: async (data: {
    email: string;
    full_name: string;
    password: string;
    role?: string;
    team_id?: string;
  }): Promise<User> => {
    const response = await apiClient.post<User>('/auth/register', data);
    return response.data;
  },
};


// -------------------------------------------------------
// Chat API
// -------------------------------------------------------

export const chatApi = {
  sendMessage: async (params: {
    messages: ChatMessage[];
    model?: string;
    session_id?: string;
    temperature?: number;
    max_tokens?: number;
  }): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>('/chat/completions', params);
    return response.data;
  },

  listSessions: async (): Promise<ChatSession[]> => {
    const response = await apiClient.get<ChatSession[]>('/chat/sessions');
    return response.data;
  },

  getSession: async (sessionId: string): Promise<ChatSessionDetail> => {
    const response = await apiClient.get<ChatSessionDetail>(`/chat/sessions/${sessionId}`);
    return response.data;
  },

  /**
   * Open a streaming connection and invoke callbacks as tokens arrive.
   * Uses the native EventSource API since Axios doesn't support SSE.
   *
   * @param messages    - conversation history
   * @param model       - model alias to use
   * @param onToken     - called with each new token string
   * @param onDone      - called when streaming is complete
   * @param onError     - called on error
   */
  streamMessage: (
    messages: ChatMessage[],
    model: string | undefined,
    onToken: (token: string) => void,
    onDone: (sessionId: string) => void,
    onError: (error: string) => void,
  ): AbortController => {
    const controller = new AbortController();
    const token = localStorage.getItem('access_token');

    // We use fetch for streaming since EventSource doesn't support POST bodies
    fetch(`${BASE_URL}/chat/completions/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ messages, model, stream: true }),
      signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) {
        onError(`HTTP ${response.status}: ${response.statusText}`);
        return;
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let sessionId = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const lines = decoder.decode(value).split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') {
            onDone(sessionId);
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.error) { onError(parsed.error); return; }
            if (parsed.session_id) sessionId = parsed.session_id;
            const token = parsed.choices?.[0]?.delta?.content;
            if (token) onToken(token);
          } catch { /* skip non-JSON lines */ }
        }
      }
    }).catch((err) => {
      if (err.name !== 'AbortError') onError(err.message);
    });

    return controller;    // caller can call controller.abort() to cancel
  },
};


// -------------------------------------------------------
// Admin API
// -------------------------------------------------------

export const adminApi = {
  listTeams: async (): Promise<Team[]> => {
    const response = await apiClient.get<Team[]>('/admin/teams');
    return response.data;
  },

  createTeam: async (data: {
    name: string;
    slug: string;
    description?: string;
    allowed_models: string[];
    default_model: string;
    spend_limit_usd?: number;
    rpm_limit?: number;
  }): Promise<Team> => {
    const response = await apiClient.post<Team>('/admin/teams', data);
    return response.data;
  },

  assignUserToTeam: async (teamId: string, userId: string): Promise<void> => {
    await apiClient.post(`/admin/teams/${teamId}/assign-user`, null, {
      params: { user_id: userId },
    });
  },

  getUsageByTeam: async (days = 30): Promise<UsageSummary[]> => {
    const response = await apiClient.get<UsageSummary[]>('/admin/analytics/usage-by-team', {
      params: { days },
    });
    return response.data;
  },

  getDailyCost: async (days = 30): Promise<DailyCost[]> => {
    const response = await apiClient.get<DailyCost[]>('/admin/analytics/daily-cost', {
      params: { days },
    });
    return response.data;
  },
};
