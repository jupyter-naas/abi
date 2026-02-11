'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  X,
  Send,
  Sparkles,
  Bot,
  Loader2,
  ChevronDown,
  Infinity,
  ListTree,
  Bug,
  MessageSquare,
  Check,
  Plus,
  History,
  Download,
  Trash2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore } from '@/stores/agents';
import { useIntegrationsStore } from '@/stores/integrations';
import { useSecretsStore } from '@/stores/secrets';
import { useAuthStore } from '@/stores/auth';

import { getApiUrl, getOllamaUrl } from '@/lib/config';

const API_BASE = getApiUrl();

type Mode = 'agent' | 'plan' | 'debug' | 'ask';

const modes: { id: Mode; label: string; icon: React.ElementType; shortcut?: string; description: string }[] = [
  { id: 'agent', label: 'Agent', icon: Infinity, shortcut: '⌘I', description: 'Can perform actions' },
  { id: 'plan', label: 'Plan', icon: ListTree, description: 'Proposes plans' },
  { id: 'debug', label: 'Debug', icon: Bug, description: 'Helps debug issues' },
  { id: 'ask', label: 'Ask', icon: MessageSquare, description: 'Only answers questions' },
];

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinkingDuration?: number;
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
}

export function AIPane() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setMode] = useState<Mode>('agent');
  const [showModeMenu, setShowModeMenu] = useState(false);
  const [showAgentMenu, setShowAgentMenu] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  // AI Pane has its own agent selection, defaulting to ABI (the supervisor)
  const [paneAgent, setPaneAgent] = useState<string>('abi');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const modeMenuRef = useRef<HTMLDivElement>(null);
  const modelMenuRef = useRef<HTMLDivElement>(null);

  const { contextPanelOpen, toggleContextPanel, currentWorkspaceId } = useWorkspaceStore();
  const { agents, getAgent } = useAgentsStore();
  const { providers } = useIntegrationsStore();
  const { getSecretByKey } = useSecretsStore();
  
  const currentAgent = mounted ? agents.find((a) => a.id === paneAgent) || agents.find((a) => a.id === 'abi') || agents[0] : null;
  
  // Get provider for agent with resolved secrets
  const getProviderForAgent = (agentId: string) => {
    const agent = getAgent(agentId);
    if (agent?.providerId) {
      const provider = providers.find(p => p.id === agent.providerId && p.enabled);
      if (provider) {
        // Resolve secrets to actual values
        let resolvedApiKey = provider.apiKey; // Legacy fallback
        let resolvedAccountId = provider.accountId; // Legacy fallback
        
        // Note: Secrets are server-side encrypted, we can't access actual values
        // Just use the provider's configured keys
        if (provider.apiKeySecretKey) {
          resolvedApiKey = provider.apiKeySecretKey; // Reference to secret key
        }
        if (provider.accountIdSecretKey) {
          resolvedAccountId = provider.accountIdSecretKey; // Reference to secret key
        }
        
        return {
          ...provider,
          apiKey: resolvedApiKey,
          accountId: resolvedAccountId,
        };
      }
    }
    return null;
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when pane opens
  useEffect(() => {
    if (contextPanelOpen && mounted) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [contextPanelOpen, mounted]);

  // Close menus on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modeMenuRef.current && !modeMenuRef.current.contains(e.target as Node)) {
        setShowModeMenu(false);
      }
      if (modelMenuRef.current && !modelMenuRef.current.contains(e.target as Node)) {
        setShowAgentMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Chat session management
  const handleNewChat = () => {
    // Save current session if it has messages
    if (messages.length > 0) {
      const newSession: ChatSession = {
        id: currentSessionId || Date.now().toString(),
        title: messages[0]?.content.slice(0, 30) + '...' || 'New chat',
        messages: [...messages],
        createdAt: new Date(),
      };
      setChatSessions((prev) => {
        const existing = prev.find((s) => s.id === newSession.id);
        if (existing) {
          return prev.map((s) => (s.id === newSession.id ? newSession : s));
        }
        return [newSession, ...prev];
      });
    }
    // Start fresh
    setMessages([]);
    setCurrentSessionId(Date.now().toString());
    setShowHistory(false);
    inputRef.current?.focus();
  };

  const handleLoadSession = (session: ChatSession) => {
    // Save current first
    if (messages.length > 0 && currentSessionId) {
      setChatSessions((prev) =>
        prev.map((s) =>
          s.id === currentSessionId ? { ...s, messages: [...messages] } : s
        )
      );
    }
    setMessages(session.messages);
    setCurrentSessionId(session.id);
    setShowHistory(false);
  };

  const handleDeleteSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setChatSessions((prev) => prev.filter((s) => s.id !== sessionId));
    if (currentSessionId === sessionId) {
      setMessages([]);
      setCurrentSessionId(null);
    }
  };

  const handleExportChat = () => {
    if (messages.length === 0) return;
    
    const transcript = messages
      .map((m) => `${m.role === 'user' ? 'You' : 'AI'}: ${m.content}`)
      .join('\n\n');
    
    const blob = new Blob([transcript], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userContent = input.trim();
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: userContent,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Get provider for current agent (AI Pane uses paneAgent)
      const provider = getProviderForAgent(paneAgent);
      
      // Build provider payload (may be null if no provider, API will fallback to Ollama)
      const providerPayload = provider ? {
        id: provider.id,
        name: provider.name,
        type: provider.type,
        enabled: provider.enabled,
        endpoint: provider.endpoint || getOllamaUrl(),
        api_key: provider.apiKey,
        account_id: provider.accountId,
        model: provider.model,
      } : null;

      // Get agent's system prompt
      const agentData = getAgent(paneAgent);
      const systemPrompt = agentData?.systemPrompt || null;
      
      // Build message history
      const fullHistory = [...messages, userMessage].map(m => ({ role: m.role, content: m.content }));

      // Add placeholder for streaming response
      const assistantId = (Date.now() + 1).toString();
      const thinkingStartTime = Date.now();
      setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '▌' }]);

      const token = useAuthStore.getState().token;
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: userContent,
          messages: fullHistory,
          agent: paneAgent,
          provider: providerPayload,
          system_prompt: systemPrompt,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let thinkingContent = '';
      let responseContent = '';
      let isInThinking = false;

      if (reader) {
        let hasError = false;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;
              
              try {
                const parsed = JSON.parse(data);
                if (parsed.content) {
                  const token = parsed.content as string;
                  
                  if (token.includes('<think>')) {
                    isInThinking = true;
                    const assembled = `<think>${thinkingContent}</think>`;
                    setMessages((prev) => 
                      prev.map((m) => m.id === assistantId ? { ...m, content: assembled } : m)
                    );
                    continue;
                  }
                  
                  if (token.includes('</think>')) {
                    isInThinking = false;
                    const assembled = `<think>${thinkingContent}</think>\n\n▌`;
                    setMessages((prev) => 
                      prev.map((m) => m.id === assistantId ? { ...m, content: assembled } : m)
                    );
                    continue;
                  }
                  
                  if (isInThinking) {
                    thinkingContent += token;
                    const assembled = `<think>${thinkingContent}</think>`;
                    setMessages((prev) => 
                      prev.map((m) => m.id === assistantId ? { ...m, content: assembled } : m)
                    );
                    continue;
                  }
                  
                  responseContent += token;
                  const assembled = thinkingContent
                    ? `<think>${thinkingContent}</think>\n\n${responseContent}▌`
                    : `${responseContent}▌`;
                  setMessages((prev) => 
                    prev.map((m) => m.id === assistantId ? { ...m, content: assembled } : m)
                  );
                }
                if (parsed.error) {
                  hasError = true;
                  const errContent = `Error: ${parsed.error}`;
                  setMessages((prev) => 
                    prev.map((m) => m.id === assistantId ? { ...m, content: errContent } : m)
                  );
                }
              } catch {
                // Ignore parse errors
              }
            }
          }
        }
        const thinkingDuration = (Date.now() - thinkingStartTime) / 1000;
        const finalContent = thinkingContent
          ? `<think>${thinkingContent}</think>\n\n${responseContent}`
          : responseContent;
        if (!finalContent && !hasError) {
          setMessages((prev) => 
            prev.map((m) => m.id === assistantId ? { ...m, content: 'No response received.', thinkingDuration } : m)
          );
        } else {
          setMessages((prev) => 
            prev.map((m) => m.id === assistantId ? { ...m, content: finalContent, thinkingDuration } : m)
          );
        }
      }
    } catch (error) {
      console.error('AI Pane API error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setMessages((prev) => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${errorMessage}\n\nMake sure the API server is running and the agent has a configured provider.`,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const currentMode = modes.find((m) => m.id === mode) || modes[0];
  const ModeIcon = currentMode.icon;

  if (!mounted || !contextPanelOpen) return null;

  return (
    <aside className="flex h-full w-80 flex-col border-l border-border/50 bg-background">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b px-3">
        <div className="flex items-center gap-1">
          <button
            onClick={handleNewChat}
            className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            title="New chat"
          >
            <Plus size={16} />
          </button>
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={cn(
              'rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground',
              showHistory && 'bg-muted text-foreground'
            )}
            title="Chat history"
          >
            <History size={16} />
          </button>
          <button
            onClick={handleExportChat}
            disabled={messages.length === 0}
            className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed"
            title="Export conversation"
          >
            <Download size={16} />
          </button>
        </div>
        <button
          onClick={toggleContextPanel}
          className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Close"
        >
          <X size={16} />
        </button>
      </div>

      {/* History Panel */}
      {showHistory && (
        <div className="border-b bg-muted/30 p-2 max-h-48 overflow-auto">
          <div className="text-xs font-medium text-muted-foreground mb-2 px-1">Recent Chats</div>
          {chatSessions.length === 0 ? (
            <p className="text-xs text-muted-foreground px-1">No chat history</p>
          ) : (
            <div className="space-y-1">
              {chatSessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => handleLoadSession(session)}
                  className={cn(
                    'flex items-center justify-between rounded px-2 py-1.5 cursor-pointer text-xs hover:bg-muted',
                    currentSessionId === session.id && 'bg-muted'
                  )}
                >
                  <div className="flex items-center gap-2 truncate flex-1">
                    <MessageSquare size={12} className="text-muted-foreground shrink-0" />
                    <span className="truncate">{session.title}</span>
                  </div>
                  <button
                    onClick={(e) => handleDeleteSession(session.id, e)}
                    className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-auto p-3">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Bot size={40} className="mb-3 text-muted-foreground/20" />
            <p className="text-sm text-muted-foreground">How can I help you?</p>
          </div>
        ) : (
          <div className="space-y-3">
            {messages.map((message) => (
              <PaneMessage key={message.id} message={message} />
            ))}
            {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
              <div className="mr-6 flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
                <Loader2 size={14} className="animate-spin" />
                <span className="text-muted-foreground">Processing...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t p-3">
        <form onSubmit={handleSubmit}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything..."
            rows={3}
            className={cn(
              'w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none',
              'placeholder:text-muted-foreground/50',
              'focus:ring-1 focus:ring-primary/30'
            )}
            disabled={isLoading}
          />
          
          {/* Bottom bar with mode and model selectors */}
          <div className="mt-2 flex items-center justify-between">
            <div className="flex items-center gap-1">
              {/* Mode selector */}
              <div ref={modeMenuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setShowModeMenu(!showModeMenu)}
                  className={cn(
                    'flex items-center gap-1.5 rounded px-2 py-1 text-xs',
                    'hover:bg-muted',
                    showModeMenu && 'bg-muted'
                  )}
                >
                  <ModeIcon size={14} />
                  <span>{currentMode.label}</span>
                  {currentMode.shortcut && (
                    <kbd className="ml-1 rounded border bg-background px-1 text-[10px] text-muted-foreground">
                      {currentMode.shortcut}
                    </kbd>
                  )}
                </button>
                
                {showModeMenu && (
                  <div className="absolute bottom-full left-0 mb-1 w-36 rounded-lg border bg-background py-1 shadow-lg">
                    {modes.map((m) => {
                      const Icon = m.icon;
                      return (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            setMode(m.id);
                            setShowModeMenu(false);
                          }}
                          className={cn(
                            'flex w-full items-center gap-2 px-3 py-1.5 text-sm',
                            'hover:bg-muted',
                            mode === m.id && 'bg-muted'
                          )}
                        >
                          <Icon size={14} />
                          <span className="flex-1 text-left">{m.label}</span>
                          {m.shortcut && (
                            <kbd className="rounded border bg-background px-1 text-[10px] text-muted-foreground">
                              {m.shortcut}
                            </kbd>
                          )}
                          {mode === m.id && <Check size={12} />}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Agent selector (AI Pane has its own selection, defaults to ABI) */}
              <div ref={modelMenuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setShowAgentMenu(!showAgentMenu)}
                  className={cn(
                    'flex items-center gap-1.5 rounded px-2 py-1 text-xs',
                    'hover:bg-muted',
                    showAgentMenu && 'bg-muted'
                  )}
                >
                  <span>{currentAgent?.name || 'ABI'}</span>
                  <ChevronDown size={12} className="text-muted-foreground" />
                </button>
                
                {showAgentMenu && (
                  <div className="absolute bottom-full left-0 mb-1 w-48 rounded-lg border bg-background py-1 shadow-lg">
                    <div className="px-3 py-1.5 text-xs text-muted-foreground">
                      Select agent
                    </div>
                    {agents.filter(agent => agent.enabled).map((agent) => (
                      <button
                        key={agent.id}
                        type="button"
                        onClick={() => {
                          setPaneAgent(agent.id);
                          setShowAgentMenu(false);
                        }}
                        className={cn(
                          'flex w-full items-center gap-2 px-3 py-1.5 text-sm',
                          'hover:bg-muted',
                          paneAgent === agent.id && 'bg-muted'
                        )}
                      >
                        <span className="flex-1 text-left">{agent.name}</span>
                        {paneAgent === agent.id && <Check size={12} />}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Send button */}
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className={cn(
                'flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground',
                'hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50'
              )}
            >
              <Send size={14} />
            </button>
          </div>
        </form>
      </div>
    </aside>
  );
}

function PaneMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  const [showThinking, setShowThinking] = useState(false);
  const [autoCollapsed, setAutoCollapsed] = useState(false);
  const wasProcessingRef = useRef(false);

  // Parse <think> tags
  const parseThinking = (content: string) => {
    const match = content.match(/<think>([\s\S]*?)<\/think>/);
    if (match) {
      const thinking = match[1].trim();
      const response = content.replace(/<think>[\s\S]*?<\/think>/, '').trim();
      return { thinking, response };
    }
    return { thinking: null, response: content };
  };

  const { thinking, response } = isUser
    ? { thinking: null, response: message.content }
    : parseThinking(message.content);

  const isStillProcessing = !isUser && thinking && (!response || response === '▌');

  // Auto-close thinking 3s after processing finishes
  useEffect(() => {
    if (isStillProcessing) {
      wasProcessingRef.current = true;
    } else if (wasProcessingRef.current && !autoCollapsed) {
      const timer = setTimeout(() => {
        setShowThinking(false);
        setAutoCollapsed(true);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [isStillProcessing, autoCollapsed]);

  const formatDuration = (seconds: number) => {
    if (seconds < 1) return '<1s';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const hasThinkingSection = !isUser && (thinking || (message.thinkingDuration && message.thinkingDuration > 0));

  if (isUser) {
    return (
      <div className="ml-6 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    );
  }

  return (
    <div className="mr-6 space-y-1">
      {/* Processing / Processed indicator */}
      {hasThinkingSection && (
        <div>
          <button
            onClick={() => thinking && setShowThinking(!showThinking)}
            className={cn(
              'flex items-center gap-1 text-[10px] text-muted-foreground transition-colors',
              thinking && 'hover:text-foreground cursor-pointer'
            )}
            disabled={!thinking}
          >
            {isStillProcessing ? (
              <span className="font-medium animate-pulse">Processing...</span>
            ) : (
              <span className="font-medium">
                Processed in {formatDuration(message.thinkingDuration || 0)}
              </span>
            )}
            {thinking && (
              <ChevronDown
                size={10}
                className={cn('transition-transform', (showThinking || (isStillProcessing && !autoCollapsed)) && 'rotate-180')}
              />
            )}
          </button>

          {thinking && (showThinking || (isStillProcessing && !autoCollapsed)) && (
            <div className="mt-1 max-h-32 overflow-y-auto rounded border border-border/50 bg-muted/50 px-2 py-1.5 text-[10px] text-muted-foreground">
              <p className="whitespace-pre-wrap leading-relaxed">{thinking}</p>
            </div>
          )}
        </div>
      )}

      {/* Response bubble */}
      <div className="rounded-lg bg-muted px-3 py-2 text-sm prose prose-sm dark:prose-invert max-w-none [&_p]:my-0.5 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0 [&_code]:bg-background/50 [&_code]:px-1 [&_code]:rounded [&_code]:text-xs">
        {isStillProcessing ? (
          <span className="inline-flex items-center gap-0.5">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '0ms' }} />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '150ms' }} />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '300ms' }} />
          </span>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{response}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
