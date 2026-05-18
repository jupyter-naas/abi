'use client';

import { useState, useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  X,
  Send,
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
  Terminal,
  FileCode,
  FileEdit,
  Play,
  BookOpen,
  CheckCircle2,
  Circle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore } from '@/stores/agents';
import { useIntegrationsStore } from '@/stores/integrations';
import { useSecretsStore } from '@/stores/secrets';
import { useAuthStore } from '@/stores/auth';
import { useFilesStore } from '@/stores/files';

import { getApiUrl, getOllamaUrl } from '@/lib/config';

const getApiBase = () => getApiUrl();

type Mode = 'agent' | 'plan' | 'debug' | 'ask';

const modes: { id: Mode; label: string; icon: React.ElementType; shortcut?: string; description: string }[] = [
  { id: 'agent', label: 'Agent', icon: Infinity, shortcut: '⌘I', description: 'Can perform actions' },
  { id: 'plan', label: 'Plan', icon: ListTree, description: 'Proposes plans' },
  { id: 'debug', label: 'Debug', icon: Bug, description: 'Helps debug issues' },
  { id: 'ask', label: 'Ask', icon: MessageSquare, description: 'Only answers questions' },
];

// ─── Opencode event types ────────────────────────────────────────────────────

interface ToolEvent {
  callId: string;
  tool: string;  // read | write | edit | bash
  path?: string;
  command?: string;
  status: 'running' | 'completed';
  output?: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinkingDuration?: number;
  toolEvents?: ToolEvent[];  // opencode tool activity
  isOpencode?: boolean;      // rendered differently
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
}


// ─── Opencode tool event card ─────────────────────────────────────────────────

const TOOL_ICONS: Record<string, React.ElementType> = {
  read: BookOpen,
  write: FileCode,
  edit: FileEdit,
  bash: Play,
};

function ToolEventCard({ event }: { event: ToolEvent }) {
  const Icon = TOOL_ICONS[event.tool] ?? Terminal;
  const label = event.path ?? event.command ?? event.tool;
  const done = event.status === 'completed';
  return (
    <div className={cn(
      'flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] transition-colors',
      done
        ? 'border-border/30 bg-muted/20 text-muted-foreground'
        : 'border-emerald-500/30 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400'
    )}>
      {done
        ? <CheckCircle2 size={11} className="flex-shrink-0 text-emerald-500" />
        : <Circle size={11} className="flex-shrink-0 animate-pulse" />
      }
      <Icon size={11} className="flex-shrink-0" />
      <span className="font-medium capitalize">{event.tool}</span>
      <span className="flex-1 truncate font-mono opacity-70">{label}</span>
    </div>
  );
}

// ─── Code suggestions (above input, fills the textarea on click) ─────────────

const CODE_SUGGESTIONS = [
  'Create a hello world HTML page with a gradient design',
  'Create a Python script that prints Fibonacci numbers',
  'Create a README.md for this module',
];

function CodeSuggestions({ onSuggest }: { onSuggest: (text: string) => void }) {
  return (
    <div className="flex flex-col gap-1 border-t px-3 pt-2 pb-1">
      {CODE_SUGGESTIONS.map((s) => (
        <button
          key={s}
          onClick={() => onSuggest(s)}
          className={cn(
            'w-full rounded-lg border border-border/60 bg-muted/40 px-3 py-2 text-left text-xs transition-all',
            'hover:border-primary/50 hover:bg-primary/5 hover:text-primary'
          )}
        >
          {s}
        </button>
      ))}
    </div>
  );
}

const OPENCODE_AGENT_ID = 'opencode';

export function AIPane() {
  const pathname = usePathname();
  const isCodeSection = pathname?.includes('/code') ?? false;
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
  // opencode thread ID — kept across messages so opencode has full conversation context
  const [opencodeSessionId, setOpencodeSessionId] = useState<string>(() => `nexus-${Date.now()}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const modeMenuRef = useRef<HTMLDivElement>(null);
  const modelMenuRef = useRef<HTMLDivElement>(null);

  const { contextPanelOpen, toggleContextPanel, currentWorkspaceId, paneAgent, setPaneAgent } = useWorkspaceStore();
  const { agents, getAgent } = useAgentsStore();
  const { providers } = useIntegrationsStore();
  const { getSecretByKey } = useSecretsStore();
  const { activeFile, fileContents, fsActiveFile, refreshFsFiles, readFsFile, setFsDiffs, clearFsDiffs } = useFilesStore();

  const isOpencode = paneAgent === OPENCODE_AGENT_ID;
  const currentAgent = mounted
    ? isOpencode
      ? null  // opencode is not in the agents store
      : agents.find((a) => a.id === paneAgent) || agents.find((a) => a.id === 'abi') || agents[0]
    : null;

  // Auto-select opencode when entering the Code section
  useEffect(() => {
    if (isCodeSection && paneAgent !== OPENCODE_AGENT_ID) {
      setPaneAgent(OPENCODE_AGENT_ID);
    }
  }, [isCodeSection]); // eslint-disable-line react-hooks/exhaustive-deps
  
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
    if (messages.length > 0) {
      const newSession: ChatSession = {
        id: currentSessionId || Date.now().toString(),
        title: messages[0]?.content.slice(0, 30) + '...' || 'New chat',
        messages: [...messages],
        createdAt: new Date(),
      };
      setChatSessions((prev) => {
        const existing = prev.find((s) => s.id === newSession.id);
        if (existing) return prev.map((s) => (s.id === newSession.id ? newSession : s));
        return [newSession, ...prev];
      });
    }
    setMessages([]);
    setCurrentSessionId(Date.now().toString());
    // New opencode session for each new chat
    setOpencodeSessionId(`nexus-${Date.now()}`);
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

  // ─── Opencode submit (used on /code route) ────────────────────────────────

  const handleOpencodeSubmit = async (userContent: string) => {
    const assistantId = (Date.now() + 1).toString();
    const textParts: Record<string, string> = {};

    clearFsDiffs();

    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', toolEvents: [], isOpencode: true },
    ]);

    const token = useAuthStore.getState().token;
    const response = await fetch(`${getApiBase()}/api/opencode/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message: userContent, session_id: opencodeSessionId }),
    });

    if (!response.ok) {
      throw new Error(`opencode API error: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      console.error('[opencode] no response body reader');
      return;
    }

    let buffer = '';

    outer: while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;

        let event: Record<string, unknown>;
        try {
          event = JSON.parse(raw) as Record<string, unknown>;
        } catch {
          console.warn('[opencode] failed to parse event:', raw.slice(0, 120));
          continue;
        }

        const eventType = event.type as string;
        const props = (event.properties ?? {}) as Record<string, unknown>;

        // ── Done / error ──────────────────────────────────────────────
        if (eventType === 'done' || eventType === 'error') {
          if (eventType === 'error') {
            const msg = (event.message as string) ?? 'opencode error';
            console.error('[opencode] stream error:', msg);
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, content: `Error: ${msg}` } : m))
            );
          }
          break outer;
        }

        if (eventType === 'session.idle') { break outer; }

        // ── session.diff — live filesystem refresh ────────────────────
        if (eventType === 'session.diff') {
          const diff = (props.diff ?? []) as Array<{ file: string; additions: number; deletions: number; status: string }>;
          if (diff.length > 0) {
            setFsDiffs(diff);
            // Fire-and-forget: refresh tree and reload active file if changed
            refreshFsFiles().then(() => {
              const currentActive = useFilesStore.getState().fsActiveFile;
              if (currentActive && diff.some((d) => currentActive.endsWith(d.file))) {
                readFsFile(currentActive);
              }
            });
          }
          continue;
        }

        if (eventType !== 'message.part.updated') continue;

        const part = (props.part ?? {}) as Record<string, unknown>;
        const partType = part.type as string;

        // ── Text parts ────────────────────────────────────────────────
        if (partType === 'text') {
          const partId = (part.id as string) ?? 'default';
          textParts[partId] = (part.text as string) ?? '';
          const fullText = Object.values(textParts).join('');
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: fullText } : m))
          );
        }

        // ── Tool parts ────────────────────────────────────────────────
        if (partType === 'tool') {
          const callId = (part.callID as string) ?? String(Date.now());
          const toolName = (part.tool as string) ?? 'tool';
          // opencode nests the input inside state: state.input.filePath
          const state = (part.state ?? {}) as Record<string, unknown>;
          const stateInput = (state.input ?? {}) as Record<string, unknown>;
          const filePath =
            (stateInput.filePath as string) ??
            (stateInput.path as string) ??
            undefined;
          const command = (stateInput.command as string) ?? undefined;
          const output = (state.output as string) ?? undefined;
          const status = (state.status as string) === 'completed' ? 'completed' : 'running';

          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              const existing = (m.toolEvents ?? []).find((t) => t.callId === callId);
              const updated: ToolEvent = existing
                ? { ...existing, status, output }
                : { callId, tool: toolName, path: filePath, command, status, output };
              const toolEvents = existing
                ? (m.toolEvents ?? []).map((t) => (t.callId === callId ? updated : t))
                : [...(m.toolEvents ?? []), updated];
              return { ...m, toolEvents };
            })
          );
        }
      }
    }
  };

  // ─── Regular chat submit ───────────────────────────────────────────────────

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
      // ── Route to opencode when opencode agent is selected ───────────────
      if (isOpencode) {
        await handleOpencodeSubmit(userContent);
        return;
      }

      // ── Regular Nexus chat ──────────────────────────────────────────────
      const provider = getProviderForAgent(paneAgent);
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

      const agentData = getAgent(paneAgent);
      let systemPrompt = agentData?.systemPrompt || null;
      if (activeFile) {
        const content = fileContents[activeFile];
        const fileContext = content !== undefined
          ? `\n\nCurrent open file: ${activeFile}\n\`\`\`\n${content.slice(0, 8000)}\n\`\`\``
          : `\n\nCurrent open file: ${activeFile} (not yet loaded)`;
        systemPrompt = (systemPrompt || 'You are a helpful coding assistant.') + fileContext;
      }

      const fullHistory = [...messages, userMessage].map(m => ({ role: m.role, content: m.content }));
      const assistantId = (Date.now() + 1).toString();
      const thinkingStartTime = Date.now();
      setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '▌' }]);
      setIsLoading(false);

      const token = useAuthStore.getState().token;
      const response = await fetch(`${getApiBase()}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
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

      if (!response.ok) throw new Error(`API error: ${response.status}`);

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
          for (const line of chunk.split('\n')) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);
            if (data === '[DONE]') continue;
            try {
              const parsed = JSON.parse(data);
              if (parsed.content) {
                const tok = parsed.content as string;
                if (tok.includes('<think>')) { isInThinking = true; continue; }
                if (tok.includes('</think>')) {
                  isInThinking = false;
                  setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: `<think>${thinkingContent}</think>\n\n▌` } : m));
                  continue;
                }
                if (isInThinking) {
                  thinkingContent += tok;
                  setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: `<think>${thinkingContent}</think>` } : m));
                  continue;
                }
                responseContent += tok;
                const assembled = thinkingContent ? `<think>${thinkingContent}</think>\n\n${responseContent}▌` : `${responseContent}▌`;
                setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: assembled } : m));
              }
              if (parsed.error) throw new Error(parsed.error);
            } catch (parseError) {
              if (!(parseError instanceof SyntaxError)) throw parseError;
            }
          }
        }
        const thinkingDuration = (Date.now() - thinkingStartTime) / 1000;
        const finalContent = thinkingContent ? `<think>${thinkingContent}</think>\n\n${responseContent}` : responseContent;
        setMessages((prev) => prev.map((m) => m.id === assistantId ? { ...m, content: finalContent, thinkingDuration } : m));
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

  const contextFile = isCodeSection ? fsActiveFile : activeFile;

  return (
    <aside className="flex h-full w-80 flex-col border-l border-border/50 bg-background">
      {/* Active file context pill */}
      {contextFile && (
        <div className="flex items-center gap-1.5 border-b bg-muted/20 px-3 py-1.5 text-[11px] text-muted-foreground">
          <FileCode size={10} className="flex-shrink-0" />
          <span className="flex-1 truncate font-mono">{contextFile.split('/').pop()}</span>
          <span className="flex-shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">in context</span>
        </div>
      )}
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

      {/* Suggestions — shown when opencode is selected and chat is empty */}
      {isOpencode && messages.length === 0 && (
        <CodeSuggestions onSuggest={(text) => { setInput(text); setTimeout(() => inputRef.current?.focus(), 50); }} />
      )}

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

              {/* Agent selector */}
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
                  {isOpencode && <Terminal size={12} className="text-emerald-500" />}
                  <span className={cn(isOpencode && 'text-emerald-600 dark:text-emerald-400 font-medium')}>
                    {isOpencode ? 'opencode' : (currentAgent?.name || 'Agent')}
                  </span>
                  <ChevronDown size={12} className="text-muted-foreground" />
                </button>

                {showAgentMenu && (
                  <div className="absolute bottom-full left-0 mb-1 w-52 rounded-lg border bg-background py-1 shadow-lg">
                    <div className="px-3 py-1.5 text-xs text-muted-foreground">Select agent</div>

                    {/* opencode — always available, pinned at top */}
                    <button
                      type="button"
                      onClick={() => { setPaneAgent(OPENCODE_AGENT_ID); setShowAgentMenu(false); }}
                      className={cn(
                        'flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-muted',
                        isOpencode && 'bg-muted'
                      )}
                    >
                      <Terminal size={13} className="text-emerald-500 flex-shrink-0" />
                      <span className="flex-1 text-left">opencode</span>
                      <span className="text-[10px] text-muted-foreground">coding agent</span>
                      {isOpencode && <Check size={12} className="flex-shrink-0" />}
                    </button>

                    {/* Separator */}
                    <div className="my-1 border-t border-border/50" />

                    {/* Regular agents */}
                    {agents.filter(a => a.enabled).sort((a, b) => a.name.localeCompare(b.name)).map((agent) => (
                      <button
                        key={agent.id}
                        type="button"
                        onClick={() => { setPaneAgent(agent.id); setShowAgentMenu(false); }}
                        className={cn(
                          'flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-muted',
                          paneAgent === agent.id && 'bg-muted'
                        )}
                      >
                        <span className="flex-1 text-left">{agent.name}</span>
                        {paneAgent === agent.id && <Check size={12} className="flex-shrink-0" />}
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
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const wasProcessingRef = useRef(false);
  const processingStartRef = useRef<number | null>(null);

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

  const isStillProcessing = Boolean(
    !isUser && thinking && (!response || response === '▌')
  );

  // Live elapsed timer while processing
  useEffect(() => {
    if (isStillProcessing) {
      if (processingStartRef.current === null) {
        processingStartRef.current = Date.now();
        setElapsedSeconds(0);
      }
      const interval = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - (processingStartRef.current ?? Date.now())) / 1000));
      }, 1000);
      return () => clearInterval(interval);
    } else {
      processingStartRef.current = null;
    }
  }, [isStillProcessing]);

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

  // Opencode assistant message with tool activity
  if (!isUser && message.isOpencode) {
    const isStreaming = !message.content || message.content.endsWith('▌');
    return (
      <div className="mr-6 space-y-1.5">
        {/* Tool events */}
        {(message.toolEvents ?? []).length > 0 && (
          <div className="space-y-0.5">
            {(message.toolEvents ?? []).map((ev) => (
              <ToolEventCard key={ev.callId} event={ev} />
            ))}
          </div>
        )}
        {/* Text response */}
        {message.content ? (
          <div className="rounded-lg bg-muted px-3 py-2 text-sm prose prose-sm dark:prose-invert max-w-none [&_p]:my-0.5 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0 [&_code]:bg-background/50 [&_code]:px-1 [&_code]:rounded [&_code]:text-xs">
            {isStreaming ? (
              <span className="inline-flex items-center gap-0.5">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '0ms' }} />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '150ms' }} />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '300ms' }} />
              </span>
            ) : (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            )}
          </div>
        ) : (message.toolEvents ?? []).length === 0 ? (
          <div className="rounded-lg bg-muted px-3 py-2 text-sm">
            <span className="inline-flex items-center gap-0.5">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '0ms' }} />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '150ms' }} />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: '300ms' }} />
            </span>
          </div>
        ) : null}
      </div>
    );
  }

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
              thinking && !isStillProcessing && 'hover:text-foreground cursor-pointer'
            )}
            disabled={!thinking || isStillProcessing}
          >
            {isStillProcessing ? (
              <span className="font-medium tabular-nums">{formatDuration(elapsedSeconds)}</span>
            ) : (
              <span className="font-medium">
                Processed in {formatDuration(message.thinkingDuration || 0)}
              </span>
            )}
            {thinking && !isStillProcessing && (
              <ChevronDown
                size={10}
                className={cn('transition-transform', showThinking && 'rotate-180')}
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
