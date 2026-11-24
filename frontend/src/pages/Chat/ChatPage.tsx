// ============================================================
// src/pages/Chat/ChatPage.tsx — Main Chat Interface
//
// ARCHITECT'S NOTE:
//   This is the primary end-user page. It mirrors the UX of
//   ChatGPT/Claude — sidebar with sessions, main chat window,
//   model selector, and real-time streaming output.
//
//   The key difference from a consumer app is model selection
//   is constrained to what the user's team policy allows.
// ============================================================

import React, { useEffect, useRef, useState } from 'react';
import { useChatStore } from '@/store/chatStore';
import { useAuthStore } from '@/store/authStore';
import { ChatMessage } from '@/types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send, Plus, MessageSquare, Loader2, AlertCircle, ChevronDown } from 'lucide-react';

// Available models — in a real app these would come from GET /v1/models
// filtered by the user's team policy
const MODEL_OPTIONS = [
  { alias: 'claude-haiku',  label: 'Claude Haiku',  tier: 'Economy'  },
  { alias: 'claude-sonnet', label: 'Claude Sonnet', tier: 'Standard' },
  { alias: 'claude-opus',   label: 'Claude Opus',   tier: 'Premium'  },
  { alias: 'gpt-4o-mini',   label: 'GPT-4o Mini',  tier: 'Economy'  },
  { alias: 'gpt-4o',        label: 'GPT-4o',        tier: 'Premium'  },
];

export const ChatPage: React.FC = () => {
  const {
    sessions, messages, isStreaming, streamingContent,
    activeSessionId, selectedModel, error,
    loadSessions, loadSession, sendMessage, setSelectedModel, newSession, clearError,
  } = useChatStore();

  const { user } = useAuthStore();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { loadSessions(); }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    const content = input.trim();
    setInput('');
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    await sendMessage(content);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-resize textarea
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  return (
    <div className="flex h-screen">
      {/* Session Sidebar */}
      <aside className="w-60 bg-gray-50 border-r border-gray-200 flex flex-col">
        <div className="p-3 border-b border-gray-200">
          <button
            onClick={newSession}
            className="w-full flex items-center gap-2 px-3 py-2 bg-white border border-gray-200
                       rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => loadSession(session.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors ${
                activeSessionId === session.id
                  ? 'bg-brand-100 text-brand-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5 inline mr-2 opacity-60" />
              {session.title ?? 'New conversation'}
            </button>
          ))}
          {sessions.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-4">No conversations yet</p>
          )}
        </div>
      </aside>

      {/* Chat Main Area */}
      <div className="flex-1 flex flex-col">
        {/* Top Bar */}
        <header className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-white">
          <div>
            <h1 className="font-semibold text-gray-900">AI Assistant</h1>
            <p className="text-xs text-gray-400">
              {user?.team_id ? 'Team workspace' : 'No team assigned'}
            </p>
          </div>

          {/* Model Selector */}
          <div className="relative">
            <select
              value={selectedModel ?? ''}
              onChange={(e) => setSelectedModel(e.target.value || undefined)}
              className="appearance-none pl-3 pr-8 py-1.5 text-sm border border-gray-200 rounded-lg
                         bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer"
            >
              <option value="">Team Default</option>
              {MODEL_OPTIONS.map((m) => (
                <option key={m.alias} value={m.alias}>
                  {m.label} ({m.tier})
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && !isStreaming && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 bg-brand-100 rounded-2xl flex items-center justify-center mb-4">
                <MessageSquare className="w-8 h-8 text-brand-600" />
              </div>
              <h2 className="text-xl font-semibold text-gray-700 mb-2">
                How can I help you today?
              </h2>
              <p className="text-gray-400 text-sm max-w-sm">
                Ask a question, draft a document, analyze data, or write code.
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}

          {/* Streaming response (tokens arriving in real-time) */}
          {isStreaming && (
            <MessageBubble
              message={{ role: 'assistant', content: streamingContent }}
              isStreaming
            />
          )}

          {/* Error state */}
          {error && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
              <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm text-red-700">{error}</p>
                <button onClick={clearError} className="text-xs text-red-500 underline mt-1">Dismiss</button>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 bg-white px-6 py-4">
          <div className="flex items-end gap-3 max-w-4xl mx-auto">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleTextareaInput}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              rows={1}
              placeholder="Message the AI… (Shift+Enter for new line)"
              className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent
                         disabled:bg-gray-50 disabled:text-gray-400"
              style={{ minHeight: '48px', maxHeight: '200px' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className="flex-shrink-0 w-10 h-10 rounded-xl bg-brand-600 hover:bg-brand-700
                         disabled:bg-gray-200 text-white flex items-center justify-center transition-colors"
            >
              {isStreaming
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Send className="w-4 h-4" />
              }
            </button>
          </div>
          <p className="text-center text-xs text-gray-400 mt-2">
            AI responses may be inaccurate. Verify important information.
          </p>
        </div>
      </div>
    </div>
  );
};


// ---- Message Bubble sub-component ----
interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, isStreaming }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
        isUser ? 'bg-brand-600 text-white' : 'bg-gray-200 text-gray-600'
      }`}>
        {isUser ? 'U' : 'AI'}
      </div>

      {/* Bubble */}
      <div className={`max-w-2xl rounded-2xl px-4 py-3 text-sm ${
        isUser
          ? 'bg-brand-600 text-white rounded-tr-sm'
          : 'bg-gray-100 text-gray-800 rounded-tl-sm'
      }`}>
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm max-w-none prose-pre:bg-gray-800 prose-pre:text-gray-100">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content || ''}
            </ReactMarkdown>
            {isStreaming && (
              <span className="inline-block w-1 h-4 bg-brand-500 ml-0.5 animate-pulse" />
            )}
          </div>
        )}
      </div>
    </div>
  );
};
