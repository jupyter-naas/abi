'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
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
import type { AgentType } from '@/stores/workspace';
import { useAgentsStore } from '@/stores/agents';
import { useIntegrationsStore } from '@/stores/integrations';
import { useSecretsStore } from '@/stores/secrets';
import { useAuthStore } from '@/stores/auth';
import { useFilesStore } from '@/stores/files';

import { getApiUrl, getOllamaUrl } from '@/lib/config';

const getApiBase = () => getApiUrl();
const OPENCODE_URL = 'http://127.0.0.1:4242';

// --- opencode session management ---
let _opencodeSessionId: string | null = null;

async function getOrCreateOpencodeSession(): Promise<string> {
  if (_opencodeSessionId) return _opencodeSessionId;
  const r = await fetch(`${OPENCODE_URL}/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      // Auto-approve all tool calls so bash/write don't block on approval
      permission: [
        { permission: 'bash',    pattern: '*', action: 'allow' },
        { permission: 'write',   pattern: '*', action: 'allow' },
        { permission: 'edit',    pattern: '*', action: 'allow' },
        { permission: 'delete',  pattern: '*', action: 'allow' },
        { permission: 'patch',   pattern: '*', action: 'allow' },
      ],
    }),
  });
  const s = await r.json();
  _opencodeSessionId = s.id as string;
  return _opencodeSessionId;
}

async function sendOpencodeMessage(sessionId: string, text: string): Promise<void> {
  await fetch(`${OPENCODE_URL}/session/${sessionId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parts: [{ type: 'text', text }] }),
  });
}

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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const modeMenuRef = useRef<HTMLDivElement>(null);
  const modelMenuRef = useRef<HTMLDivElement>(null);

  const { contextPanelOpen, toggleContextPanel, currentWorkspaceId, paneAgent, setPaneAgent } = useWorkspaceStore();
  const { agents, getAgent } = useAgentsStore();
  const { providers } = useIntegrationsStore();
  const { getSecretByKey } = useSecretsStore();

  // opencode state (used when paneAgent === 'opencode')
  const [opencodeReady, setOpencodeReady] = useState(false);
  const opencodeEsRef = useRef<EventSource | null>(null);
  const opencodeSessionRef = useRef<string | null>(null);
  const currentAssistantIdRef = useRef<string | null>(null); // mirrors closure var for polling

  // Probe opencode availability
  useEffect(() => {
    const check = () =>
      fetch(`${OPENCODE_URL}/session`, { mode: 'cors' })
        .then((r) => r.ok && setOpencodeReady(true))
        .catch(() => setOpencodeReady(false));
    check();
    const id = setInterval(check, 8000);
    return () => clearInterval(id);
  }, []);

  // Subscribe to opencode SSE when it's the active agent
  useEffect(() => {
    if (paneAgent !== 'opencode' || !opencodeReady) return;

    const es = new EventSource(`${OPENCODE_URL}/event`);
    opencodeEsRef.current = es;
    let currentAssistantId: string | null = null;

    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data) as { type: string; properties: Record<string, unknown> };
        const evSessionId = (ev.properties?.sessionID as string | undefined);

        // Ignore events from other sessions (only apply to session-specific events)
        const isOurSession = !evSessionId || !opencodeSessionRef.current || evSessionId === opencodeSessionRef.current;

        // Ensure the assistant bubble exists, keyed by messageID
        const ensureBubble = (msgId: string) => {
          if (!currentAssistantId) {
            currentAssistantId = msgId;
            currentAssistantIdRef.current = msgId;
            setMessages((prev) => {
              if (prev.find((m) => m.id === msgId)) return prev;
              return [...prev, { id: msgId, role: 'assistant' as const, content: '▌' }];
            });
          }
        };

        // Auto-reload active file from disk so previews reflect agent edits
        const reloadActiveFile = () => {
          const { activeFile, readHostFile, unsavedChanges } = useFilesStore.getState();
          if (!activeFile) return;
          readHostFile(activeFile).then(() => {
            useFilesStore.setState((s) => ({
              unsavedChanges: { ...s.unsavedChanges, [activeFile]: false },
            }));
          });
        };

        const finishStream = () => {
          if (currentAssistantId) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === currentAssistantId
                  ? { ...m, content: m.content.replace(/▌$/, '') }
                  : m
              )
            );
            currentAssistantId = null;
            currentAssistantIdRef.current = null;
          }
          setIsLoading(false);
          reloadActiveFile();
        };

        // Streaming delta (primary path for streaming text)
        if (ev.type === 'message.part.delta' && isOurSession) {
          const { messageID, field, delta } = ev.properties as {
            sessionID: string; messageID: string; partID: string; field: string; delta: string;
          };
          ensureBubble(messageID);
          if (field === 'text') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === currentAssistantId
                  ? { ...m, content: m.content.replace(/▌$/, '') + delta + '▌' }
                  : m
              )
            );
          }
        }

        // Part completed — show tool calls
        if (ev.type === 'message.part.updated' && isOurSession) {
          const { part } = ev.properties as {
            sessionID: string;
            part: { messageID: string; type: string; tool?: string; toolName?: string; state?: { status?: string } };
          };
          ensureBubble(part.messageID);
          // "tool" is the opencode type (not "tool-invocation")
          if ((part.type === 'tool' || part.type === 'tool-invocation' || part.type === 'tool_call') && currentAssistantId) {
            const name = part.tool || part.toolName || 'tool';
            const done = (part.state as Record<string,unknown>)?.status === 'completed';
            const toolLabel = `\`${name}\`${done ? ' ✓' : ' …'}`;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === currentAssistantId
                  ? { ...m, content: m.content.replace(/▌$/, '') + `\n> ${toolLabel}\n▌` }
                  : m
              )
            );
          }
        }

        // Session finished — two possible event types
        if ((ev.type === 'session.idle' || ev.type === 'session.status') && isOurSession) {
          const status = (ev.properties?.status as Record<string,unknown> | undefined)?.type;
          if (ev.type === 'session.idle' || status === 'idle') {
            finishStream();
          }
        }
      } catch { /* ignore */ }
    };

    return () => { es.close(); opencodeEsRef.current = null; };
  }, [paneAgent, opencodeReady]);
  
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

    // Route to opencode when selected
    if (paneAgent === 'opencode') {
      try {
        if (!opencodeReady) throw new Error('opencode is not running. Run `make opencode-start` from ~/aia');
        const sessionId = opencodeSessionRef.current ?? await getOrCreateOpencodeSession();
        opencodeSessionRef.current = sessionId;
        await sendOpencodeMessage(sessionId, userContent);
        // Response arrives via SSE in the useEffect above; isLoading cleared on session.idle
        // Safety polling: if SSE misses session.idle, poll until last assistant msg is complete
        const pollSessionId = sessionId;
        const poll = async () => {
          // Grace period for SSE to try first
          await new Promise((r) => setTimeout(r, 3000));
          for (let i = 0; i < 120; i++) {
            try {
              const r = await fetch(`${OPENCODE_URL}/session/${pollSessionId}/message`);
              if (r.ok) {
                const msgs = await r.json() as Array<{ info: { role: string; time?: { completed?: number } } }>;
                const lastAssistant = [...msgs].reverse().find((m) => m.info.role === 'assistant');
                if (lastAssistant?.info.time?.completed) {
                  // session complete — clean up cursor if still showing
                  const aid = currentAssistantIdRef.current;
                  if (aid) {
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === aid ? { ...m, content: m.content.replace(/▌$/, '') } : m
                      )
                    );
                    currentAssistantIdRef.current = null;
                    setIsLoading(false);
                  }
                  // Reload active file regardless of cursor state
                  const { activeFile: af, readHostFile } = useFilesStore.getState();
                  if (af) readHostFile(af).then(() => {
                    useFilesStore.setState((s) => ({
                      unsavedChanges: { ...s.unsavedChanges, [af]: false },
                    }));
                  });
                  return;
                }
              }
            } catch { /* ignore poll errors */ }
            await new Promise((r) => setTimeout(r, 1000));
          }
        };
        poll();
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'opencode error';
        setMessages((prev) => [...prev, { id: Date.now().toString(), role: 'assistant', content: `⚠️ ${msg}` }]);
        setIsLoading(false);
      }
      return;
    }

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
      
      // Build message history for the API (must include the current user message)
      // Note: React setState is async, so `messages` doesn't have userMessage yet.
      // We manually append it, matching how chat-interface uses getState() for fresh data.
      const fullHistory = [...messages, userMessage].map(m => ({ role: m.role, content: m.content }));

      // Add placeholder for streaming response
      const assistantId = (Date.now() + 1).toString();
      const thinkingStartTime = Date.now();
      setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '▌' }]);
      setIsLoading(false); // Stop loading indicator, streaming will show the cursor

      const token = useAuthStore.getState().token;
      const response = await fetch(`${getApiBase()}/api/chat/stream`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          workspace_id: currentWorkspaceId,
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
                  
                  // Track <think> tags
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
                  
                  // Regular response content
                  responseContent += token;
                  const assembled = thinkingContent
                    ? `<think>${thinkingContent}</think>\n\n${responseContent}▌`
                    : `${responseContent}▌`;
                  setMessages((prev) => 
                    prev.map((m) => m.id === assistantId ? { ...m, content: assembled } : m)
                  );
                }
                if (parsed.error) {
                  const errContent = `Error: ${parsed.error}`;
                  setMessages((prev) => 
                    prev.map((m) => m.id === assistantId ? { ...m, content: errContent } : m)
                  );
                  throw new Error(parsed.error);
                }
              } catch (parseError) {
                // Only swallow JSON parsing failures for partial SSE chunks
                if (!(parseError instanceof SyntaxError)) {
                  throw parseError;
                }
              }
            }
          }
        }
        // Final: store full content with thinking duration
        const thinkingDuration = (Date.now() - thinkingStartTime) / 1000;
        const finalContent = thinkingContent
          ? `<think>${thinkingContent}</think>\n\n${responseContent}`
          : responseContent;
        setMessages((prev) => 
          prev.map((m) => m.id === assistantId ? { ...m, content: finalContent, thinkingDuration } : m)
        );
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

              {/* Agent selector (AI Pane has its own selection, defaults to SupervisorAgent) */}
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
                  <span>{paneAgent === 'opencode' ? 'opencode' : (currentAgent?.name || 'SupervisorAgent')}</span>
                  <ChevronDown size={12} className="text-muted-foreground" />
                </button>
                
                {showAgentMenu && (
                  <div className="absolute bottom-full left-0 mb-1 w-48 rounded-lg border bg-background py-1 shadow-lg">
                    <div className="px-3 py-1.5 text-xs text-muted-foreground">
                      Select agent
                    </div>
                    {/* opencode — local coding agent with filesystem + shell */}
                    <button
                      type="button"
                      onClick={() => { setPaneAgent('opencode' as AgentType); setShowAgentMenu(false); }}
                      className={cn(
                        'flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-muted',
                        paneAgent === 'opencode' && 'bg-muted'
                      )}
                    >
                      <span className={cn(
                        'h-1.5 w-1.5 rounded-full flex-shrink-0',
                        opencodeReady ? 'bg-emerald-400' : 'bg-zinc-500'
                      )} />
                      <span className="flex-1 text-left">opencode</span>
                      {paneAgent === 'opencode' && <Check size={12} />}
                    </button>
                    <div className="mx-2 my-1 h-px bg-border" />
                    {agents.filter(agent => agent.enabled).sort((a, b) => a.name.localeCompare(b.name)).map((agent) => (
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
