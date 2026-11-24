// ============================================================
// src/store/chatStore.ts — Chat State (Zustand)
// ============================================================

import { create } from 'zustand';
import { ChatMessage, ChatSession } from '@/types';
import { chatApi } from '@/services/api';

interface ChatState {
  sessions: ChatSession[];
  activeSessionId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  streamingContent: string;
  selectedModel: string | undefined;
  error: string | null;

  // Actions
  loadSessions: () => Promise<void>;
  loadSession: (sessionId: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  setSelectedModel: (model: string | undefined) => void;
  newSession: () => void;
  clearError: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  messages: [],
  isStreaming: false,
  streamingContent: '',
  selectedModel: undefined,
  error: null,

  loadSessions: async () => {
    const sessions = await chatApi.listSessions();
    set({ sessions });
  },

  loadSession: async (sessionId: string) => {
    const session = await chatApi.getSession(sessionId);
    set({
      activeSessionId: sessionId,
      messages: session.messages,
    });
  },

  sendMessage: async (content: string) => {
    const { messages, activeSessionId, selectedModel } = get();
    const userMessage: ChatMessage = { role: 'user', content };
    const updatedMessages = [...messages, userMessage];

    // Optimistic UI update — show user message immediately
    set({ messages: updatedMessages, isStreaming: true, streamingContent: '', error: null });

    // Stream the response token-by-token
    let accumulatedContent = '';
    let newSessionId = activeSessionId;

    const controller = chatApi.streamMessage(
      updatedMessages,
      selectedModel,
      // onToken: append each arriving token to the streaming buffer
      (token) => {
        accumulatedContent += token;
        set({ streamingContent: accumulatedContent });
      },
      // onDone: finalize the message when streaming ends
      (sessionId) => {
        newSessionId = sessionId || activeSessionId;
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: accumulatedContent,
        };
        set((state) => ({
          messages: [...state.messages, assistantMessage],
          isStreaming: false,
          streamingContent: '',
          activeSessionId: newSessionId,
        }));
        // Refresh session list to show updated title/timestamp
        get().loadSessions();
      },
      // onError: surface the error to the UI
      (errorMsg) => {
        set({
          isStreaming: false,
          streamingContent: '',
          error: `AI Error: ${errorMsg}`,
          // Remove the optimistic user message on error so user can retry
          messages: messages,
        });
      },
    );

    // Store controller so user can cancel streaming (future feature)
    // For now, it's captured in closure
    void controller;
  },

  setSelectedModel: (model) => set({ selectedModel: model }),

  newSession: () => set({ activeSessionId: null, messages: [] }),

  clearError: () => set({ error: null }),
}));
