'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
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
  Paperclip,
  ChevronRight,
  Folder,
  StopCircle,
  Undo2,
  Cpu,
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

interface OcModel {
  providerID: string;
  modelID: string;
  name: string;
}

interface OcProvider {
  id: string;
  name: string;
  models: OcModel[];
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
  const [showFilePicker, setShowFilePicker] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<string[]>([]);
  const filePickerRef = useRef<HTMLDivElement>(null);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  // opencode thread ID — kept across messages so opencode has full conversation context
  const [opencodeSessionId, setOpencodeSessionId] = useState<string>(() => `nexus-${Date.now()}`);
  // Model picker (opencode only)
  const [opencodeProviders, setOpencodeProviders] = useState<OcProvider[]>([]);
  const [selectedOcModel, setSelectedOcModel] = useState<OcModel | null>(null);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const modelPickerRef = useRef<HTMLDivElement>(null);
  // Abort support
  const streamReaderRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const modeMenuRef = useRef<HTMLDivElement>(null);
  const modelMenuRef = useRef<HTMLDivElement>(null);

  const { contextPanelOpen, toggleContextPanel, currentWorkspaceId, paneAgent, setPaneAgent } = useWorkspaceStore();
  const { agents, getAgent } = useAgentsStore();
  const { providers } = useIntegrationsStore();
  const { getSecretByKey } = useSecretsStore();
  const { activeFile, fileContents, fsActiveFile, refreshFsFiles, readFsFile, setFsDiffs, clearFsDiffs, fsFiles, fsFolderContents, fetchFsFolderContents } = useFilesStore();

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
      if (filePickerRef.current && !filePickerRef.current.contains(e.target as Node)) {
        setShowFilePicker(false);
      }
      if (modelPickerRef.current && !modelPickerRef.current.contains(e.target as Node)) {
        setShowModelPicker(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch opencode providers when opencode is active
  const fetchOcProviders = useCallback(async () => {
    try {
      const token = useAuthStore.getState().token;
      const r = await fetch(`${getApiBase()}/api/opencode/providers`, {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!r.ok) return;
      const data = await r.json();
      // opencode returns { providers: [{ id, name, models: { modelId: {...} } }] }
      // Normalize models dict -> array
      const rawList: Array<{ id: string; name?: string; models?: Record<string, { id?: string; name?: string }> | Array<{ id?: string; name?: string }> }> =
        Array.isArray(data) ? data : (data.providers ?? []);
      const list: OcProvider[] = rawList
        .filter((p) => p.id)
        .map((p) => ({
          id: p.id,
          name: p.name ?? p.id,
          models: Array.isArray(p.models)
            ? p.models.map((m) => ({ providerID: p.id, modelID: m.id ?? '', name: m.name ?? m.id ?? '' }))
            : Object.values(p.models ?? {}).map((m) => ({ providerID: p.id, modelID: m.id ?? '', name: m.name ?? m.id ?? '' })),
        }))
        // Only show providers with at least one usable model
        .filter((p) => p.models.length > 0);
      setOpencodeProviders(list);
    } catch { /* opencode not available */ }
  }, []);

  useEffect(() => {
    if (isOpencode && mounted) fetchOcProviders();
  }, [isOpencode, mounted, fetchOcProviders]);

  // Fetch real opencode sessions when history panel opens
  const fetchOcSessions = useCallback(async () => {
    try {
      const token = useAuthStore.getState().token;
      const r = await fetch(`${getApiBase()}/api/opencode/sessions`, {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!r.ok) return;
      const data = await r.json();
      const sessions = (Array.isArray(data) ? data : []) as Array<{ id: string; title?: string; updatedAt?: string }>;
      setChatSessions(
        sessions.map((s) => ({
          id: s.id,
          title: s.title ?? s.id.slice(0, 24),
          messages: [],
          createdAt: new Date(s.updatedAt ?? Date.now()),
        }))
      );
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (showHistory && isOpencode) fetchOcSessions();
  }, [showHistory, isOpencode, fetchOcSessions]);

  // Read file content for attachments (uses the filesystem API)
  const readAttachmentContent = async (path: string): Promise<string> => {
    try {
      const content = await readFsFile(path);
      return content ?? '';
    } catch {
      return '';
    }
  };

  const toggleAttachment = (path: string) => {
    setAttachedFiles((prev) =>
      prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path]
    );
  };

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

  const handleLoadSession = async (session: ChatSession) => {
    if (isOpencode) {
      try {
        const token = useAuthStore.getState().token;
        const r = await fetch(`${getApiBase()}/api/opencode/sessions/${session.id}/messages`, {
          headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        });
        if (r.ok) {
          const raw = await r.json() as Array<{ id?: string; role?: string; parts?: Array<{ type: string; text?: string }> }>;
          const converted: Message[] = raw.flatMap((m) => {
            const role = (m.role === 'user' ? 'user' : 'assistant') as 'user' | 'assistant';
            const text = (m.parts ?? [])
              .filter((p) => p.type === 'text')
              .map((p) => p.text ?? '')
              .join('');
            if (!text) return [];
            return [{ id: m.id ?? String(Date.now()), role, content: text, isOpencode: role === 'assistant' }];
          });
          setMessages(converted);
          setOpencodeSessionId(session.id);
          setCurrentSessionId(session.id);
          setShowHistory(false);
          return;
        }
      } catch { /* fall through to in-memory */ }
    }
    if (messages.length > 0 && currentSessionId) {
      setChatSessions((prev) =>
        prev.map((s) => (s.id === currentSessionId ? { ...s, messages: [...messages] } : s))
      );
    }
    setMessages(session.messages);
    setCurrentSessionId(session.id);
    setShowHistory(false);
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (isOpencode) {
      try {
        const token = useAuthStore.getState().token;
        await fetch(`${getApiBase()}/api/opencode/sessions/${sessionId}`, {
          method: 'DELETE',
          headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        });
      } catch { /* ignore */ }
    }
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

  // ─── Abort (stop mid-stream) ───────────────────────────────────────────────

  const handleAbort = useCallback(async () => {
    try {
      if (streamReaderRef.current) {
        await streamReaderRef.current.cancel();
        streamReaderRef.current = null;
      }
      const token = useAuthStore.getState().token;
      await fetch(`${getApiBase()}/api/opencode/sessions/${opencodeSessionId}/abort`, {
        method: 'POST',
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
    } catch { /* ignore */ } finally {
      setIsLoading(false);
    }
  }, [opencodeSessionId]);

  // ─── Revert (undo last exchange) ──────────────────────────────────────────

  const handleRevert = useCallback(async () => {
    try {
      const token = useAuthStore.getState().token;
      await fetch(`${getApiBase()}/api/opencode/sessions/${opencodeSessionId}/revert`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({}),
      });
    } catch { /* ignore */ }
    // Remove last assistant + its preceding user message from local state
    setMessages((prev) => {
      const lastAssIdx = [...prev].reverse().findIndex((m) => m.role === 'assistant');
      if (lastAssIdx === -1) return prev;
      const trimAt = prev.length - 1 - lastAssIdx;
      const before = prev.slice(0, trimAt);
      const lastUserIdx = [...before].reverse().findIndex((m) => m.role === 'user');
      if (lastUserIdx === -1) return before;
      return before.slice(0, before.length - 1 - lastUserIdx);
    });
  }, [opencodeSessionId]);

  // ─── Opencode submit (used on /code route) ────────────────────────────────

  const handleOpencodeSubmit = async (userContent: string) => {
    const assistantId = (Date.now() + 1).toString();
    const textParts: Record<string, string> = {};

    clearFsDiffs();

    // Prepend attached file contents as fenced code blocks
    let messageWithAttachments = userContent;
    if (attachedFiles.length > 0) {
      const blocks = await Promise.all(
        attachedFiles.map(async (path) => {
          const content = await readAttachmentContent(path);
          const ext = path.split('.').pop() ?? '';
          return `[Attached file: ${path}]\n\`\`\`${ext}\n${content}\n\`\`\``;
        })
      );
      messageWithAttachments = blocks.join('\n\n') + '\n\n' + userContent;
      setAttachedFiles([]);
    }

    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', toolEvents: [], isOpencode: true },
    ]);

    const token = useAuthStore.getState().token;
    const chatBody: Record<string, unknown> = { message: messageWithAttachments, session_id: opencodeSessionId };
    if (selectedOcModel) {
      chatBody.model_provider_id = selectedOcModel.providerID;
      chatBody.model_id = selectedOcModel.modelID;
    }
    const response = await fetch(`${getApiBase()}/api/opencode/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(chatBody),
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
    streamReaderRef.current = reader;

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
          streamReaderRef.current = null;
          break outer;
        }

        if (eventType === 'session.idle') { streamReaderRef.current = null; break outer; }

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
    <aside className={cn('flex h-full flex-col border-l border-border/50 bg-background', isCodeSection ? 'w-96' : 'w-80')}>
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
          {/* Attached file chips */}
          {attachedFiles.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1">
              {attachedFiles.map((path) => (
                <span key={path} className="flex items-center gap-1 rounded-full border border-border/60 bg-muted/50 px-2 py-0.5 text-[11px] font-mono text-muted-foreground">
                  <FileCode size={10} className="flex-shrink-0 text-primary" />
                  <span className="max-w-[140px] truncate">{path.split('/').pop()}</span>
                  <button type="button" onClick={() => toggleAttachment(path)} className="ml-0.5 rounded-full hover:text-destructive">
                    <X size={10} />
                  </button>
                </span>
              ))}
            </div>
          )}

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

              {/* Model picker — opencode only */}
              {isOpencode && opencodeProviders.length > 0 && (
                <div ref={modelPickerRef} className="relative">
                  <button
                    type="button"
                    onClick={() => setShowModelPicker((v) => !v)}
                    title="Select model"
                    className={cn(
                      'flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
                      (showModelPicker || selectedOcModel) && 'text-foreground'
                    )}
                  >
                    <Cpu size={11} />
                    <span className="max-w-[80px] truncate">
                      {selectedOcModel ? selectedOcModel.name || selectedOcModel.modelID : 'default'}
                    </span>
                    <ChevronDown size={10} />
                  </button>

                  {showModelPicker && (
                    <div className="absolute bottom-full left-0 mb-1 w-64 rounded-lg border bg-background py-1 shadow-lg max-h-64 overflow-y-auto">
                      <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground">Model</div>
                      {/* Default (use EngineConfiguration model) */}
                      <button
                        type="button"
                        onClick={() => { setSelectedOcModel(null); setShowModelPicker(false); }}
                        className={cn('flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted', !selectedOcModel && 'bg-muted')}
                      >
                        <span className="flex-1 text-left text-muted-foreground italic">Default (from config)</span>
                        {!selectedOcModel && <Check size={11} />}
                      </button>
                      <div className="my-1 border-t border-border/40" />
                      {opencodeProviders.map((prov) => (
                        <div key={prov.id}>
                          <div className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                            {prov.name || prov.id}
                          </div>
                          {(prov.models ?? []).map((m) => {
                            const isSelected = selectedOcModel?.providerID === prov.id && selectedOcModel?.modelID === m.modelID;
                            return (
                              <button
                                key={m.modelID}
                                type="button"
                                onClick={() => { setSelectedOcModel({ ...m, providerID: prov.id }); setShowModelPicker(false); }}
                                className={cn('flex w-full items-center gap-2 px-3 py-1 text-xs hover:bg-muted', isSelected && 'bg-muted')}
                              >
                                <span className="flex-1 truncate text-left font-mono">{m.name || m.modelID}</span>
                                {isSelected && <Check size={10} />}
                              </button>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center gap-1">
              {/* Revert last exchange — opencode only, when there are messages */}
              {isOpencode && !isLoading && messages.length > 0 && (
                <button
                  type="button"
                  onClick={handleRevert}
                  title="Undo last exchange"
                  className="flex h-7 w-7 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <Undo2 size={14} />
                </button>
              )}

              {/* Attach file button — opencode only */}
              {isOpencode && (
                <div ref={filePickerRef} className="relative">
                  <button
                    type="button"
                    onClick={() => setShowFilePicker((v) => !v)}
                    title="Attach file"
                    className={cn(
                      'flex h-7 w-7 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
                      (showFilePicker || attachedFiles.length > 0) && 'text-primary'
                    )}
                  >
                    <Paperclip size={14} />
                  </button>

                  {showFilePicker && (
                    <div className="absolute bottom-full right-0 mb-2 w-64 rounded-lg border bg-background shadow-lg">
                      <div className="border-b px-3 py-2 text-[11px] font-medium text-muted-foreground">Attach from sandbox</div>
                      <div className="max-h-56 overflow-y-auto py-1">
                        <FileBrowserTree
                          files={fsFiles}
                          fetchChildren={fetchFsFolderContents}
                          attached={attachedFiles}
                          onToggle={toggleAttachment}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Abort button (while streaming) or Send button */}
              {isOpencode && isLoading ? (
                <button
                  type="button"
                  onClick={handleAbort}
                  title="Stop generation"
                  className="flex h-7 w-7 items-center justify-center rounded-full bg-destructive/80 text-destructive-foreground transition-colors hover:bg-destructive"
                >
                  <StopCircle size={14} />
                </button>
              ) : (
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
              )}
            </div>
          </div>
        </form>
      </div>
    </aside>
  );
}

// ─── Inline file browser for attachment picker ────────────────────────────────

import type { FileInfo } from '@/stores/files';

function FileBrowserTree({
  files, fetchChildren, attached, onToggle, depth = 0,
}: {
  files: FileInfo[];
  fetchChildren: (path: string) => Promise<FileInfo[]>;
  attached: string[];
  onToggle: (path: string) => void;
  depth?: number;
}) {
  if (files.length === 0) {
    return (
      <p className="px-3 py-2 text-[11px] italic text-muted-foreground">
        {depth === 0 ? 'Sandbox is empty' : 'Empty folder'}
      </p>
    );
  }
  return (
    <>
      {files.map((f) => (
        <FileBrowserNode
          key={f.path}
          file={f}
          fetchChildren={fetchChildren}
          attached={attached}
          onToggle={onToggle}
          depth={depth}
        />
      ))}
    </>
  );
}

function FileBrowserNode({
  file, fetchChildren, attached, onToggle, depth,
}: {
  file: FileInfo;
  fetchChildren: (path: string) => Promise<FileInfo[]>;
  attached: string[];
  onToggle: (path: string) => void;
  depth: number;
}) {
  const isFolder = file.type === 'folder';
  const isAttached = attached.includes(file.path);
  const [expanded, setExpanded] = useState(false);
  const [children, setChildren] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    if (isFolder) {
      if (!expanded && children.length === 0) {
        setLoading(true);
        const data = await fetchChildren(file.path);
        setChildren(data);
        setLoading(false);
      }
      setExpanded((v) => !v);
    } else {
      onToggle(file.path);
    }
  };

  return (
    <div>
      <button
        type="button"
        onClick={toggle}
        className={cn(
          'flex w-full items-center gap-1.5 px-2 py-1 text-[11px] transition-colors hover:bg-muted',
          isAttached && 'bg-primary/10 text-primary'
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {isFolder ? (
          <>
            <ChevronRight size={10} className={cn('flex-shrink-0 text-muted-foreground transition-transform', expanded && 'rotate-90', loading && 'animate-pulse')} />
            <Folder size={11} className="flex-shrink-0 text-muted-foreground" />
          </>
        ) : (
          <>
            <span className="w-2.5 flex-shrink-0" />
            <FileCode size={11} className={cn('flex-shrink-0', isAttached ? 'text-primary' : 'text-muted-foreground')} />
          </>
        )}
        <span className={cn('flex-1 truncate text-left font-mono', isAttached && 'font-medium')}>{file.name}</span>
        {isAttached && <Check size={10} className="flex-shrink-0 text-primary" />}
      </button>

      {isFolder && expanded && (
        <FileBrowserTree
          files={children}
          fetchChildren={fetchChildren}
          attached={attached}
          onToggle={onToggle}
          depth={depth + 1}
        />
      )}
    </div>
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
      <div className="space-y-1.5">
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
          <div className="rounded-lg bg-muted px-3 py-2 text-sm prose prose-sm dark:prose-invert max-w-none [&_p]:my-0.5 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0 [&_code]:bg-background/50 [&_code]:px-1 [&_code]:rounded [&_code]:text-xs [&_pre]:overflow-x-auto">
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
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-3 py-2 text-sm text-primary-foreground">
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
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

      {/* Response bubble — full width, no indent, matches opencode style */}
      <div className="rounded-2xl rounded-tl-sm bg-muted px-3 py-2 text-sm prose prose-sm dark:prose-invert max-w-none [&_p]:my-0.5 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0 [&_code]:bg-background/50 [&_code]:px-1 [&_code]:rounded [&_code]:text-xs [&_pre]:overflow-x-auto">
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
