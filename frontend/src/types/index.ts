// ============================================================
// src/types/index.ts — Shared TypeScript types
//
// ARCHITECT'S NOTE:
//   These types mirror the Pydantic schemas in the FastAPI backend.
//   Keeping them in sync is critical — a mismatch causes silent
//   runtime bugs (TypeScript only checks at compile time, not runtime).
//
//   In a larger project, consider generating these types automatically
//   from the OpenAPI spec using tools like openapi-typescript.
// ============================================================

// -------------------------------------------------------
// Auth
// -------------------------------------------------------

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  team_id: string | null;
  is_active: boolean;
}

export type UserRole = 'super_admin' | 'team_admin' | 'member';

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// -------------------------------------------------------
// Chat
// -------------------------------------------------------

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatSession {
  id: string;
  title: string | null;
  model_used: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export interface ChatResponse {
  session_id: string;
  message: ChatMessage;
  model_used: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  cost_usd: number | null;
}

// -------------------------------------------------------
// Models
// -------------------------------------------------------

export interface ModelInfo {
  alias: string;
  description: string;
  tier: 'economy' | 'standard' | 'premium';
  provider: string;
}

// -------------------------------------------------------
// Admin / Analytics
// -------------------------------------------------------

export interface Team {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
  member_count: number;
}

export interface UsageSummary {
  team_name: string;
  total_calls: number;
  total_tokens: number;
  total_cost_usd: number;
  top_model: string | null;
}

export interface DailyCost {
  date: string;
  cost_usd: number;
  calls: number;
}

// -------------------------------------------------------
// UI State
// -------------------------------------------------------

export interface ApiError {
  detail: string;
  status: number;
}
