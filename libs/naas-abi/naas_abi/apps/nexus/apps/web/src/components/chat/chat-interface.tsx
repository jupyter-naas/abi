'use client';

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Send, Plus, Bot, User, AlertCircle, Brain, ChevronDown, X, Globe, ArrowUp, Download, ExternalLink, HardDrive, RefreshCw, Loader2 } from 'lucide-react';
import Image from 'next/image';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, type AgentType, type Message } from '@/stores/workspace';
import { useIntegrationsStore } from '@/stores/integrations';
import { useAgentsStore } from '@/stores/agents';
import { useSecretsStore } from '@/stores/secrets';
import { useAuthStore } from '@/stores/auth';
import { useWebSocket } from '@/contexts/websocket-context';
import { AgentSelector } from './agent-selector';
import { TypingIndicator } from '@/components/typing-indicator';

import { getApiUrl, getOllamaUrl } from '@/lib/config';

const getApiBase = () => getApiUrl();

// Helper to get logo URL (prefix relative URLs with API base)
const getLogoUrl = (url: string | null): string | undefined => {
  if (!url) return undefined;
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  return `${getApiBase()}${url}`; // Relative URL -> add API base
};

// Max image size for uploads (5MB)
const MAX_IMAGE_SIZE = 5 * 1024 * 1024;
const SUPPORTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
const SUPPORTED_DOCUMENT_EXTENSIONS = ['pdf', 'docx', 'pptx', 'txt', 'md', 'json', 'csv'];
const ATTACHMENT_ACCEPT = 'image/jpeg,image/png,image/gif,image/webp,.pdf,.docx,.pptx,.txt,.md,.json,.csv';

// Match http(s) URLs for linkification and preview
const URL_REGEX = /https?:\/\/[^\s<>\]\)]+?(?=[\s<>\]\)]|$)/g;

/** Split text into segments; URLs become anchor elements so they get href styling and preview */
function linkifyText(text: string, isUser: boolean): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  URL_REGEX.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = URL_REGEX.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const url = match[0];
    parts.push(
      <React.Fragment key={key++}>
        <LinkWithPreview href={url} isUserBubble={isUser}>
          {url}
        </LinkWithPreview>
      </React.Fragment>
    );
    lastIndex = match.index + url.length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts.length === 1 && typeof parts[0] === 'string' ? parts[0] : parts;
}

/** Styled link with hover card: open in new tab only. Rendered via portal so it stays above chat list/input. */
function LinkWithPreview({
  href,
  children,
  isUserBubble,
}: {
  href: string;
  children: React.ReactNode;
  isUserBubble?: boolean;
}) {
  const linkRef = useRef<HTMLAnchorElement>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  const linkClass = isUserBubble
    ? 'text-white underline underline-offset-2 hover:opacity-90 break-all'
    : 'text-workspace-accent hover:text-workspace-accent/90 underline underline-offset-2 break-all';

  const domain = (() => {
    try {
      return new URL(href).hostname;
    } catch {
      return href;
    }
  })();

  const handleMouseEnter = () => {
    const el = linkRef.current;
    if (el) {
      const rect = el.getBoundingClientRect();
      setPosition({ left: rect.left, top: rect.bottom + 4 });
    }
    setShowPreview(true);
  };

  const handleMouseLeave = () => {
    setShowPreview(false);
    setPosition(null);
  };

  const cardContent =
    showPreview && position ? (
      <span
        className="fixed flex w-72 max-w-[90vw] flex-col overflow-hidden rounded-lg border border-border bg-popover shadow-lg"
        style={{ left: position.left, top: position.top, zIndex: 99999 }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <div className="p-3">
          <p className="text-xs font-medium text-foreground line-clamp-1">{domain}</p>
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 flex items-center gap-1.5 text-xs text-workspace-accent hover:underline"
          >
            <ExternalLink size={12} />
            Open in new tab
          </a>
        </div>
      </span>
    ) : null;

  return (
    <>
      <a
        ref={linkRef}
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={linkClass}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        {children}
      </a>
      {typeof document !== 'undefined' && cardContent && createPortal(cardContent, document.body)}
    </>
  );
}

export function ChatInterface() {
  const [mounted, setMounted] = useState(false);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const streamControllerRef = useRef<AbortController | null>(null);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [showConnecting, setShowConnecting] = useState(false);
  const gotFirstTokenRef = useRef(false);
  const connectingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [attachedImages, setAttachedImages] = useState<string[]>([]); // Base64 images
  const [imageError, setImageError] = useState<string | null>(null);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [searchEnabled, setSearchEnabled] = useState(false); // Force web search
  const fileInputRef = useRef<HTMLInputElement>(null);
  // My Drive picker state
  const [showMyDrivePicker, setShowMyDrivePicker] = useState(false);
  const [myDriveFiles, setMyDriveFiles] = useState<Array<{name: string; path: string; type: string}>>([]);
  const [myDriveLoading, setMyDriveLoading] = useState(false);
  const [myDrivePath, setMyDrivePath] = useState('');
  const myDrivePickerRef = useRef<HTMLDivElement>(null);
  // Per-job ingestion status tracking
  const [ingestionJobs, setIngestionJobs] = useState<Map<string, {filename: string; status: string; progress?: number; error?: string; conversationId: string}>>(new Map());
  const ingestionAbortRefs = useRef<Map<string, AbortController>>(new Map());
  const [isDragOver, setIsDragOver] = useState(false);
  const dragCounterRef = useRef(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const {
    activeConversationId,
    selectedAgent,
    createConversation,
    addMessage,
    updateLastMessage,
    getWorkspaceConversations,
    currentWorkspaceId,
    loadConversationMessages,
  } = useWorkspaceStore();

  const { socket, startTyping, stopTyping, onMessage } = useWebSocket();

  const { providers, getProviderForAgent: getLegacyProviderForAgent } = useIntegrationsStore();
  const { getAgent } = useAgentsStore();
  const { getSecretByKey } = useSecretsStore();
  
  // Get provider for current agent - check agents store first, then legacy mapping
  const getProviderForAgent = (agentId: string) => {
    const agent = getAgent(agentId);
    let provider = null;
    
    if (agent?.provider) {
      // Find enabled integration matching the agent's provider type
      // E.g., agent.provider = "xai" → find provider with type = "xai"
      provider = providers.find(p => p.type === agent.provider && p.enabled);
      
      // Override the model if agent specifies one
      if (provider && agent.modelId) {
        provider = { ...provider, model: agent.modelId };
      }
    } else if (agent?.providerId) {
      // DEPRECATED: Legacy providerId mapping (backward compat)
      provider = providers.find(p => p.id === agent.providerId && p.enabled);
    } else {
      // Fallback to legacy agent mapping
      provider = getLegacyProviderForAgent(agentId);
    }
    
    return provider;
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  // Listen for new messages from WebSocket
  useEffect(() => {
    if (!activeConversationId) return;
    
    const cleanup = onMessage((data) => {
      if (data.conversation_id === activeConversationId) {
        addMessage(activeConversationId, data.message);
      }
    });
    
    return cleanup;
  }, [activeConversationId, onMessage, addMessage]);

  useEffect(() => {
    if (!activeConversationId) return;
    if (!activeConversationId.startsWith('conv-')) return;
    const conv = useWorkspaceStore
      .getState()
      .conversations.find((c) => c.id === activeConversationId);
    // If this thread came from backend list (no messages loaded yet), fetch full history.
    if (!conv || conv.messages.length === 0) {
      void loadConversationMessages(activeConversationId);
    }
  }, [activeConversationId, loadConversationMessages]);

  // Handle typing indicators
  const handleInputChange = (value: string) => {
    setInput(value);
    
    if (!currentWorkspaceId || !activeConversationId) return;
    
    // Start typing indicator
    if (value.length > 0) {
      startTyping(currentWorkspaceId, activeConversationId);
      
      // Clear previous timeout
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      
      // Stop typing after 3 seconds of no activity
      typingTimeoutRef.current = setTimeout(() => {
        stopTyping(currentWorkspaceId, activeConversationId);
      }, 3000);
    } else {
      // Stop typing immediately when input is cleared
      stopTyping(currentWorkspaceId, activeConversationId);
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    }
  };

  // Cleanup typing timeout on unmount
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    };
  }, []);

  // Listen for ingestion status events from the server and update per-job state
  useEffect(() => {
    if (!socket) return;

    const handleIngestionStatus = (data: any) => {
      const { job_id, status, progress, conversation_id, error, cache_hit, chunks_count } = data;
      if (!job_id) return;

      setIngestionJobs((prev) => {
        const next = new Map(prev);
        const existing = next.get(job_id);
        if (!existing) return prev;
        next.set(job_id, { ...existing, status, progress: progress ?? existing.progress, error });
        return next;
      });

      if (status === 'ready' && conversation_id) {
        setIngestionJobs((prev) => {
          const existing = prev.get(job_id);
          const filename = existing?.filename ?? 'file';
          const cacheLabel = cache_hit ? 'cache hit' : 'cache miss';
          addMessage(conversation_id, {
            role: 'system',
            content: `\`${filename}\` indexed for this chat (${cacheLabel})${chunks_count ? ` — ${chunks_count} chunks` : ''}.`,
          });
          const next = new Map(prev);
          next.delete(job_id);
          return next;
        });
        // Abort the fallback polling loop since WS delivered the result
        ingestionAbortRefs.current.get(job_id)?.abort();
        ingestionAbortRefs.current.delete(job_id);
      }

      if (status === 'failed' && conversation_id) {
        setIngestionJobs((prev) => {
          const existing = prev.get(job_id);
          const filename = existing?.filename ?? 'file';
          addMessage(conversation_id, {
            role: 'system',
            content: `Failed to index \`${filename}\`: ${error || 'Unknown error'}`,
          });
          // Keep in map so the user can retry
          const next = new Map(prev);
          if (existing) next.set(job_id, { ...existing, status: 'failed', error });
          return next;
        });
        ingestionAbortRefs.current.get(job_id)?.abort();
        ingestionAbortRefs.current.delete(job_id);
      }
    };

    socket.on('chat.ingestion.status', handleIngestionStatus);
    return () => {
      socket.off('chat.ingestion.status', handleIngestionStatus);
    };
  }, [socket, addMessage]);

  // Abort all polling loops on unmount
  useEffect(() => {
    return () => {
      ingestionAbortRefs.current.forEach((ctrl) => ctrl.abort());
    };
  }, []);

  // Close My Drive picker when clicking outside
  useEffect(() => {
    if (!showMyDrivePicker) return;
    const handler = (e: MouseEvent) => {
      if (myDrivePickerRef.current && !myDrivePickerRef.current.contains(e.target as Node)) {
        setShowMyDrivePicker(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showMyDrivePicker]);

  // Use null on server to prevent hydration mismatch
  const workspaceConversations = mounted ? getWorkspaceConversations() : [];
  const activeConversation = mounted
    ? workspaceConversations.find((c) => c.id === activeConversationId)
    : null;
  const selectedAgentData = getAgent(selectedAgent);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeConversation?.messages]);

  const isSupportedDocument = (file: File): boolean => {
    const ext = file.name.toLowerCase().split('.').pop() || '';
    return SUPPORTED_DOCUMENT_EXTENSIONS.includes(ext);
  };

  // Poll a job until done; WebSocket events will abort early when the server delivers results.
  const pollIngestionJob = async (
    jobId: string,
    filename: string,
    conversationId: string,
    token: string | null,
  ): Promise<void> => {
    const abortController = new AbortController();
    ingestionAbortRefs.current.set(jobId, abortController);

    try {
      const maxAttempts = 120;
      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        if (abortController.signal.aborted) return;

        await new Promise<void>((resolve, reject) => {
          const timer = setTimeout(resolve, 1000);
          abortController.signal.addEventListener('abort', () => {
            clearTimeout(timer);
            reject(new DOMException('Aborted', 'AbortError'));
          }, { once: true });
        });

        if (abortController.signal.aborted) return;

        let statusResponse: Response;
        try {
          statusResponse = await fetch(
            `${getApiBase()}/api/chat/ingestion-jobs/${jobId}`,
            {
              headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
              signal: abortController.signal,
            },
          );
        } catch {
          continue;
        }

        if (!statusResponse.ok) continue;

        const job = await statusResponse.json();

        // Keep local state in sync with polling result
        setIngestionJobs((prev) => {
          const next = new Map(prev);
          const existing = next.get(jobId);
          if (existing) next.set(jobId, { ...existing, status: job.status, progress: job.progress });
          return next;
        });

        if (job.status === 'ready') {
          const cacheLabel = job.cache_hit ? 'cache hit' : 'cache miss';
          addMessage(conversationId, {
            role: 'system',
            content: `\`${filename}\` indexed for this chat (${cacheLabel}).`,
          });
          setIngestionJobs((prev) => { const next = new Map(prev); next.delete(jobId); return next; });
          return;
        }

        if (job.status === 'failed') {
          // Keep in map — user can retry
          setIngestionJobs((prev) => {
            const next = new Map(prev);
            const existing = next.get(jobId);
            if (existing) next.set(jobId, { ...existing, status: 'failed', error: job.error_message });
            return next;
          });
          throw new Error(job.error_message || `Ingestion failed for ${filename}`);
        }
      }

      throw new Error(`Ingestion timeout for ${filename}`);
    } catch (err) {
      if ((err as Error).name === 'AbortError') return; // WS already handled it
      throw err;
    } finally {
      ingestionAbortRefs.current.delete(jobId);
    }
  };

  const uploadDocumentToChat = async (file: File): Promise<void> => {
    let conversationId = activeConversationId;
    if (!conversationId) {
      conversationId = createConversation();
    }

    const token = useAuthStore.getState().token;
    const formData = new FormData();
    formData.append('file', file);
    if (currentWorkspaceId) formData.append('workspace_id', currentWorkspaceId);

    const response = await fetch(
      `${getApiBase()}/api/chat/conversations/${conversationId}/files/upload`,
      {
        method: 'POST',
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: formData,
      },
    );

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload?.detail || `Failed to upload ${file.name}`);
    }

    const result = await response.json();

    if (!result.job_id) {
      // Synchronous ingestion result (small file, cache hit)
      const cacheLabel = result.cache_hit ? 'cache hit' : 'cache miss';
      addMessage(conversationId, {
        role: 'system',
        content: `\`${file.name}\` indexed for this chat (${cacheLabel}).`,
      });
      return;
    }

    setIngestionJobs((prev) => {
      const next = new Map(prev);
      next.set(result.job_id, { filename: file.name, status: 'queued', conversationId });
      return next;
    });

    await pollIngestionJob(result.job_id, file.name, conversationId, token);
  };

  const fetchMyDriveFiles = async (path = '') => {
    setMyDriveLoading(true);
    const token = useAuthStore.getState().token;
    try {
      const params = new URLSearchParams({ scope: 'my_drive', path });
      const res = await fetch(`${getApiBase()}/api/files/?${params}`, {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) return;
      const data = await res.json();
      setMyDriveFiles(
        (data.files ?? []).map((f: any) => ({ name: f.name, path: f.path, type: f.type })),
      );
      setMyDrivePath(path);
    } finally {
      setMyDriveLoading(false);
    }
  };

  const ingestFromMyDrive = async (sourcePath: string, filename: string): Promise<void> => {
    let conversationId = activeConversationId;
    if (!conversationId) {
      conversationId = createConversation();
    }
    setShowMyDrivePicker(false);

    const token = useAuthStore.getState().token;
    const res = await fetch(
      `${getApiBase()}/api/chat/conversations/${conversationId}/files/ingest`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ source_path: sourcePath, workspace_id: currentWorkspaceId }),
      },
    );

    if (!res.ok) {
      const payload = await res.json().catch(() => ({}));
      throw new Error(payload?.detail || `Failed to ingest ${filename}`);
    }

    const result = await res.json();

    if (!result.job_id) {
      const cacheLabel = result.cache_hit ? 'cache hit' : 'cache miss';
      addMessage(conversationId, {
        role: 'system',
        content: `\`${filename}\` indexed from My Drive (${cacheLabel}).`,
      });
      return;
    }

    setIngestionJobs((prev) => {
      const next = new Map(prev);
      next.set(result.job_id, { filename, status: 'queued', conversationId });
      return next;
    });

    await pollIngestionJob(result.job_id, filename, conversationId, token);
  };

  // Handle attachment selection (images + documents)
  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    
    setImageError(null);
    const newImages: string[] = [];
    let hasDocumentUpload = false;
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const isImage = SUPPORTED_IMAGE_TYPES.includes(file.type);
      const isDocument = isSupportedDocument(file);
      
      if (!isImage && !isDocument) {
        setImageError(`Unsupported file: ${file.name}. Supported: images, PDF, DOCX, PPTX, TXT, MD, JSON, CSV.`);
        continue;
      }
      
      // Validate file size
      if (file.size > MAX_IMAGE_SIZE) {
        setImageError(`File too large: ${file.name}. Max size is 5MB.`);
        continue;
      }
      
      if (isDocument) {
        hasDocumentUpload = true;
        try {
          await uploadDocumentToChat(file);
        } catch (err) {
          const detail = err instanceof Error ? err.message : `Failed to upload ${file.name}`;
          setImageError(detail);
        }
        continue;
      }

      // Convert image to base64
      const base64 = await new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onload = () => {
          const result = reader.result as string;
          // Remove the data:image/...;base64, prefix for Ollama API
          const base64Data = result.split(',')[1];
          resolve(base64Data);
        };
        reader.readAsDataURL(file);
      });
      
      newImages.push(base64);
    }
    
    setAttachedImages([...attachedImages, ...newImages]);
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    void hasDocumentUpload; // tracking is now handled by ingestionJobs state
  };

  const removeImage = (index: number) => {
    setAttachedImages(attachedImages.filter((_, i) => i !== index));
    setImageError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && attachedImages.length === 0) || isLoading) return;

    let conversationId = activeConversationId;
    const existingConversationBeforeSend = activeConversationId
      ? useWorkspaceStore.getState().conversations.find((c) => c.id === activeConversationId)
      : null;

    // Create new conversation if none active
    if (!conversationId) {
      conversationId = createConversation();
    }

    const currentImages = [...attachedImages]; // Copy before clearing
    
    // Add user message with images
    addMessage(conversationId, {
      role: 'user',
      content: input.trim() || (attachedImages.length > 0 ? 'What is in this image?' : ''),
      images: currentImages.length > 0 ? currentImages : undefined,
    });

    const userMessage = input.trim() || (currentImages.length > 0 ? 'What is in this image?' : '');
    handleInputChange('');
    setAttachedImages([]); // Clear attached images after adding to message
    setImageError(null);
    setSearchEnabled(false); // Reset search toggle after sending
    setIsLoading(true);

    try {
      // Get provider for current agent
      const provider = getProviderForAgent(selectedAgent);
      const token = useAuthStore.getState().token;
      const workspaceId = useWorkspaceStore.getState().currentWorkspaceId;

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
      const agentData = getAgent(selectedAgent);
      const systemPrompt = agentData?.systemPrompt || null;
      
      // If this is an existing thread with no local history loaded yet, fetch it first.
      if (
        existingConversationBeforeSend &&
        conversationId.startsWith('conv-') &&
        existingConversationBeforeSend.messages.length === 0
      ) {
        await loadConversationMessages(conversationId);
      }
      // Get current conversation with fresh state (including the just-added user message)
      const freshConversations = useWorkspaceStore.getState().conversations;
      const currentConversation = freshConversations.find(c => c.id === conversationId);
      const allMessages = currentConversation?.messages || [];
      
      // Build full message history for the API (including images and agent attribution for multimodal)
      const fullHistory = allMessages.map(m => ({
        role: m.role,
        content: m.content,
        images: m.images || null,
        agent: m.agent || null,  // Include agent ID for multi-agent conversations
      }));

      // Use streaming for Ollama, Cloudflare and ABI, regular for others
      // Default to streaming if no provider (Ollama fallback)
      const supportsStreaming =
        !provider ||
        provider?.type === 'ollama' ||
        provider?.type === 'cloudflare' ||
        provider?.type === 'abi';
      if (supportsStreaming) {
        setIsStreaming(true);
        setIsLoading(false); // Don't show loading dots for streaming
        
        // Track thinking time
        const thinkingStartTime = Date.now();
        
        // Add placeholder for streaming response
        addMessage(conversationId, {
          role: 'assistant',
          content: searchEnabled ? '🌐 Searching the web...' : '▌',
          agent: selectedAgent,
        });
        // Capture placeholder message id for controls
        {
          const convNow = useWorkspaceStore.getState().conversations.find(c => c.id === conversationId);
          const lastMsg = convNow?.messages[convNow.messages.length - 1];
          setStreamingMessageId(lastMsg?.id || null);
        }
        // Setup connecting indicator
        gotFirstTokenRef.current = false;
        setShowConnecting(false);
        if (connectingTimerRef.current) clearTimeout(connectingTimerRef.current);
        connectingTimerRef.current = setTimeout(() => {
          if (!gotFirstTokenRef.current) setShowConnecting(true);
        }, 700);

        let thinkingContent = '';   // Accumulated thinking text
        let responseContent = '';   // Accumulated response text
        let streamSources: string[] = [];  // RAG source filenames
        const streamEvents: string[] = [];
        const appendStreamEvent = (eventText: string) => {
          const previous = streamEvents[streamEvents.length - 1];
          if (previous !== eventText) {
            streamEvents.push(eventText);
          }
        };

        const renderStreamingMessage = (withCaret: boolean) => {
          const eventsSection = streamEvents.length > 0
            ? `🛠️ Tool activity:\n${streamEvents.map((eventText) => `- ${eventText}`).join('\n')}\n\n`
            : '';

          const body = thinkingContent
            ? `<think>${thinkingContent}</think>\n\n${responseContent}`
            : responseContent;

          const contentBody = body || '';
          const assembled = withCaret
            ? `${eventsSection}${contentBody || '▌'}${contentBody ? '▌' : ''}`
            : `${eventsSection}${contentBody}`;

          updateLastMessage(conversationId!, assembled.trimEnd() || '▌');
        };

        const formatStreamEvent = (parsed: any): string | null => {
          if (parsed?.event === 'tool') {
            const toolName = typeof parsed.tool === 'string' ? parsed.tool : 'tool';
            const status = typeof parsed.status === 'string' ? parsed.status : 'running';
            if (status === 'completed') return `${toolName} completed`;
            if (status === 'failed' || status === 'error') return `${toolName} failed`;
            if (status === 'cancelled') return `${toolName} cancelled`;
            if (status === 'pending') return `${toolName} queued`;
            return `${toolName} running`;
          }

          if (parsed?.event === 'agent.question' && typeof parsed.question === 'string') {
            return `Agent question: ${parsed.question}`;
          }

          return null;
        };

        try {
          const controller = new AbortController();
          streamControllerRef.current = controller;
          const response = await fetch(`${getApiBase()}/api/chat/stream`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          },
          signal: controller.signal,
          body: JSON.stringify({
            conversation_id: conversationId,
            workspace_id: workspaceId,
            message: userMessage,
            images: currentImages.length > 0 ? currentImages : null,
            messages: fullHistory,
            agent: selectedAgent,
            provider: providerPayload,
            system_prompt: systemPrompt,
            search_enabled: searchEnabled,
          }),
        });

        if (!response.ok) {
          // Auto-logout on 401 (invalid/expired token)
          if (response.status === 401) {
            console.warn('Auth token expired, logging out...');
            useAuthStore.getState().logout();
            window.location.href = '/auth/login';
            return;
          }
          throw new Error(`API error: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';       // Full raw content (including <think> tags)
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
                  if (parsed.sources && Array.isArray(parsed.sources)) {
                    streamSources = parsed.sources as string[];
                  }
                  if (parsed.search) {
                    appendStreamEvent('Web search in progress');
                    renderStreamingMessage(true);
                  }
                  const streamEvent = formatStreamEvent(parsed);
                  if (streamEvent) {
                    appendStreamEvent(streamEvent);
                    renderStreamingMessage(true);
                  }
                  if (parsed.content) {
                    const token = parsed.content as string;
                    fullContent += token;
                    if (!gotFirstTokenRef.current) {
                      gotFirstTokenRef.current = true;
                      if (connectingTimerRef.current) clearTimeout(connectingTimerRef.current);
                      setShowConnecting(false);
                    }
                    
                    // Track <think> tags
                    if (token.includes('<think>')) {
                      isInThinking = true;
                      renderStreamingMessage(false);
                      continue;
                    }
                    
                    if (token.includes('</think>')) {
                      isInThinking = false;
                      renderStreamingMessage(true);
                      continue;
                    }
                    
                    if (isInThinking) {
                      // Stream thinking content live
                      thinkingContent += token;
                      renderStreamingMessage(false);
                      continue;
                    }
                    
                    // Regular response content
                    responseContent += token;
                    renderStreamingMessage(true);
                  }
                  if (parsed.error) {
                    // Show error in current message and throw to trigger modal
                    fullContent = `Error: ${parsed.error}`;
                    updateLastMessage(conversationId!, fullContent);
                    throw new Error(parsed.error);
                  }
                } catch (parseError) {
                  // Re-throw non-JSON errors (e.g. provider error payloads).
                  // Only swallow JSON parsing failures for partial SSE chunks.
                  if (!(parseError instanceof SyntaxError)) {
                    throw parseError;
                  }
                }
              }
            }
          }
        }
        // Final: store full content with thinking duration
        const thinkingDuration = (Date.now() - thinkingStartTime) / 1000;
        const eventsSection = streamEvents.length > 0
          ? `🛠️ Tool activity:\n${streamEvents.map((eventText) => `- ${eventText}`).join('\n')}\n\n`
          : '';
        const finalBody = thinkingContent
          ? `<think>${thinkingContent}</think>\n\n${responseContent}`
          : responseContent;
        const finalContent = `${eventsSection}${finalBody}`.trim();
        updateLastMessage(conversationId!, finalContent, thinkingDuration, streamSources.length > 0 ? streamSources : undefined);
      } catch (streamError) {
        // Gracefully handle user-initiated aborts
        if ((streamError as any)?.name === 'AbortError') {
          const eventsSection = streamEvents.length > 0
            ? `🛠️ Tool activity:\n${streamEvents.map((eventText) => `- ${eventText}`).join('\n')}\n\n`
            : '';
          const finalBody = thinkingContent
            ? `<think>${thinkingContent}</think>\n\n${responseContent}`
            : responseContent;
          const finalContent = `${eventsSection}${finalBody}`.trim();
          if (conversationId) updateLastMessage(conversationId, finalContent, undefined, streamSources.length > 0 ? streamSources : undefined);
        } else {
          // Streaming-specific error - throw to outer catch for modal handling
          throw streamError as any;
        }
      } finally {
        setIsStreaming(false);
        setStreamingMessageId(null);
        if (connectingTimerRef.current) clearTimeout(connectingTimerRef.current);
        setShowConnecting(false);
        streamControllerRef.current = null;
      }
      } else {
        // Non-streaming for other providers
        const thinkingStartTime = Date.now();
        
        const response = await fetch(`${getApiBase()}/api/chat/complete`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            conversation_id: conversationId,
            workspace_id: workspaceId,
            message: userMessage,
            images: currentImages.length > 0 ? currentImages : null,
            messages: fullHistory,
            agent: selectedAgent,
            provider: providerPayload,
            system_prompt: systemPrompt,
          }),
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        const thinkingDuration = (Date.now() - thinkingStartTime) / 1000;

        addMessage(conversationId!, {
          role: 'assistant',
          content: data.message.content,
          agent: selectedAgent,
          thinkingDuration,
          sources: data.context_used?.length > 0 ? data.context_used : undefined,
        });
      }
    } catch (error) {
      // console.error('Chat API error:', error);
      
      // Check if it's an Ollama connection error
      // const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      // const isOllamaError = errorMessage.includes('Ollama') || errorMessage.includes('11434') || errorMessage.includes('Could not reach');
      //
      // if (isOllamaError) {
      //   // If we added a placeholder message, update it with error instead of adding new one
      //   if (conversationId && isStreaming) {
      //     updateLastMessage(conversationId, `❌ Ollama is not running or not reachable.\n\nClick below to start it automatically.`);
      //   }
      //
      //   // Show modal to user
      //   if (confirm('❌ Ollama is not running.\n\nWould you like to start Ollama and pull the required model?\n\n(This may take a few minutes on first run)')) {
      //     try {
      //       // Update the message to show we're starting
      //       if (conversationId) {
      //         updateLastMessage(conversationId, '🔄 Starting Ollama and pulling model...\n\n⏳ This may take 1-2 minutes on first run.\n\nPlease wait...');
      //       }
      //
      //       setIsLoading(true);
      //
      //       // Try to ensure Ollama is ready (will auto-start + pull model)
      //       const ensureResponse = await fetch(`${getApiBase()}/api/ollama/ensure-ready`, {
      //         method: 'POST',
      //         headers: { 'Content-Type': 'application/json' },
      //       });
      //
      //       const ensureData = await ensureResponse.json();
      //
      //       if (ensureData.ready) {
      //         // Remove the loading message before retry
      //         if (conversationId) {
      //           useWorkspaceStore.setState(state => ({
      //             conversations: state.conversations.map(c =>
      //               c.id === conversationId
      //                 ? { ...c, messages: c.messages.slice(0, -1) }
      //                 : c
      //             )
      //           }));
      //         }
      //
      //         // Retry the message automatically
      //         alert('✅ Ollama is ready! Retrying your message...');
      //         // Reconstruct and resubmit
      //         await handleSubmit(new Event('submit') as any);
      //         return;
      //       } else {
      //         // Update message with error
      //         if (conversationId) {
      //           updateLastMessage(conversationId, `⚠️ Could not start Ollama: ${ensureData.error || 'Unknown error'}\n\nPlease start Ollama manually and try again.`);
      //         }
      //       }
      //     } catch (startError) {
      //       console.error('Failed to start Ollama:', startError);
      //       if (conversationId) {
      //         updateLastMessage(conversationId, '⚠️ Failed to start Ollama automatically.\n\nPlease start it manually:\n• macOS: Open Ollama.app\n• Linux: Run `ollama serve`\n\nThen try your message again.');
      //       }
      //     } finally {
      //       setIsLoading(false);
      //     }
      //   } else {
      //     // User cancelled - remove the error message
      //     if (conversationId) {
      //       useWorkspaceStore.setState(state => ({
      //         conversations: state.conversations.map(c =>
      //           c.id === conversationId
      //             ? { ...c, messages: c.messages.slice(0, -1) }
      //             : c
      //         )
      //       }));
      //     }
      //   }
      // } else {
      // For other errors, update the placeholder if it exists, otherwise add new message
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      if (conversationId) {
          if (isStreaming) {
            updateLastMessage(conversationId, `❌ Error: ${errorMessage}\n\nPlease try again or check your provider settings.`);
          } else {
            addMessage(conversationId, {
              role: 'assistant',
              content: `❌ Error: ${errorMessage}\n\nPlease try again or check your provider settings.`,
              agent: selectedAgent,
            });
          }
        }
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
    }
  };

  const handleExportConversation = async () => {
    if (!activeConversation || activeConversation.messages.length === 0) {
      alert('No conversation to export');
      return;
    }

    try {
      // Import authFetch dynamically
      const { authFetch } = await import('@/stores/auth');
      
      // Call backend API for auditable export
      const response = await authFetch(
        `${getApiBase()}/api/chat/conversations/${activeConversation.id}/export?format=txt`
      );
      
      if (!response.ok) {
        throw new Error('Failed to export conversation');
      }
      
      // Download the file
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `conversation-${activeConversation.id}-${Date.now()}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Failed to export conversation. Please try again.');
    }
  };

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Messages area */}
      <div className="flex-1 overflow-auto p-4 min-h-0">
        {!activeConversation || activeConversation.messages.length === 0 ? (
          <EmptyState
            selectedAgentName={selectedAgentData?.name || selectedAgent}
            logoUrl={selectedAgentData?.logoUrl ?? undefined}
            suggestions={selectedAgentData?.suggestions}
            onSuggestionClick={(prompt) => setInput(prompt)}
          />
        ) : (
          <div className="mx-auto max-w-3xl space-y-6">
            {activeConversation.messages.map((message) => (
              <MessageBubble 
                key={message.id} 
                message={message} 
                showConnecting={showConnecting}
                showStop={Boolean(streamingMessageId)}
                onStop={() => {
                  streamControllerRef.current?.abort();
                }}
              />
            ))}
            {isLoading && !isStreaming && (
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-workspace-accent text-white">
                  <Bot size={16} />
                </div>
                <div className="flex items-center gap-2 rounded-2xl bg-muted px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50" />
                    <span
                      className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50"
                      style={{ animationDelay: '0.1s' }}
                    />
                    <span
                      className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50"
                      style={{ animationDelay: '0.2s' }}
                    />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="p-4">
        <div className="mx-auto max-w-3xl">
          {/* Header with Agent selector and Export button */}
          <div className="mb-2 flex items-center justify-between gap-2">
            <AgentSelector />
            
            {activeConversation && activeConversation.messages.length > 0 && (
              <button
                onClick={handleExportConversation}
                className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                title="Export conversation"
              >
                <Download size={16} />
              </button>
            )}
          </div>
          <form onSubmit={handleSubmit}>
            {/* Image previews */}
            {attachedImages.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {attachedImages.map((img, idx) => (
                  <div key={idx} className="group relative">
                    <Image
                      src={`data:image/jpeg;base64,${img}`}
                      alt={`Attached ${idx + 1}`}
                      width={80}
                      height={80}
                      className="h-20 w-20 rounded-lg border border-border object-cover"
                      unoptimized
                    />
                    <button
                      type="button"
                      onClick={() => removeImage(idx)}
                      className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-destructive-foreground opacity-0 transition-opacity group-hover:opacity-100"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            
            {/* Image error */}
            {imageError && (
              <div className="mb-2 flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
                <AlertCircle size={14} />
                {imageError}
              </div>
            )}
            {/* Per-job ingestion status (progressive + retry on failure) */}
            {ingestionJobs.size > 0 && (
              <div className="mb-2 flex flex-col gap-1">
                {Array.from(ingestionJobs.entries()).map(([jobId, job]) => {
                  const isFailed = job.status === 'failed';
                  return (
                    <div
                      key={jobId}
                      className={cn(
                        'flex items-center gap-2 rounded-lg px-3 py-2 text-xs',
                        isFailed
                          ? 'bg-destructive/10 text-destructive'
                          : 'bg-muted text-muted-foreground',
                      )}
                    >
                      {isFailed ? (
                        <AlertCircle size={14} className="shrink-0" />
                      ) : (
                        <Loader2 size={14} className="shrink-0 animate-spin" />
                      )}
                      <span className="flex-1 truncate">
                        {isFailed
                          ? `Failed: ${job.filename}${job.error ? ` — ${job.error}` : ''}`
                          : `${job.filename} — ${job.status}${job.progress != null ? ` (${job.progress}%)` : ''}`}
                      </span>
                      {isFailed && (
                        <button
                          type="button"
                          title="Retry ingestion"
                          className="ml-1 flex shrink-0 items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium hover:bg-destructive/20"
                          onClick={() => {
                            setIngestionJobs((prev) => { const next = new Map(prev); next.delete(jobId); return next; });
                            void ingestFromMyDrive(job.filename, job.filename).catch(() => {});
                          }}
                        >
                          <RefreshCw size={11} />
                          Retry
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            
            <div
              className={cn(
                'relative rounded-2xl border bg-card transition-colors',
                isDragOver
                  ? 'border-workspace-accent border-2 bg-workspace-accent/5'
                  : 'border-border/50',
              )}
              onDragEnter={(e) => {
                e.preventDefault();
                dragCounterRef.current += 1;
                if (e.dataTransfer.types.includes('Files')) setIsDragOver(true);
              }}
              onDragLeave={() => {
                dragCounterRef.current -= 1;
                if (dragCounterRef.current === 0) setIsDragOver(false);
              }}
              onDragOver={(e) => { e.preventDefault(); }}
              onDrop={(e) => {
                e.preventDefault();
                dragCounterRef.current = 0;
                setIsDragOver(false);
                const files = Array.from(e.dataTransfer.files);
                if (!files.length) return;
                const docs = files.filter((f) => !f.type.startsWith('image/'));
                const imgs = files.filter((f) => f.type.startsWith('image/'));
                docs.forEach((f) => void uploadDocumentToChat(f).catch(() => {}));
                if (imgs.length) {
                  // re-use existing image attach flow via a synthetic FileList
                  const dt = new DataTransfer();
                  imgs.forEach((f) => dt.items.add(f));
                  const synth = { target: { files: dt.files } } as unknown as React.ChangeEvent<HTMLInputElement>;
                  void handleImageSelect(synth);
                }
              }}
            >
              {isDragOver && (
                <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-2xl">
                  <span className="text-sm font-medium text-workspace-accent">Drop file to attach</span>
                </div>
              )}
              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept={ATTACHMENT_ACCEPT}
                multiple
                className="hidden"
                onChange={handleImageSelect}
              />
              
              {/* Row 1: Textarea */}
              <div className="px-4 pt-3 pb-1">
                <textarea
                  value={input}
                  onChange={(e) => handleInputChange(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                  placeholder={searchEnabled ? "Search the web..." : attachedImages.length > 0 ? "Ask about the image..." : "Send a message..."}
                  className="max-h-36 min-h-[24px] w-full resize-none bg-transparent text-sm outline-none ring-0 focus:ring-0 focus:outline-none placeholder:text-muted-foreground"
                  rows={1}
                />
              </div>
              
              {/* Row 2: Action buttons */}
              <div className="flex items-center justify-between px-3 pb-2 pt-1">
                <div className="flex items-center gap-1">
                  {/* Attach (plus) */}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-full transition-colors',
                      'text-muted-foreground hover:bg-muted hover:text-foreground',
                      attachedImages.length > 0 && 'bg-workspace-accent/15 text-workspace-accent'
                    )}
                    title="Attach image or document"
                  >
                    <Plus size={20} />
                  </button>

                  {/* My Drive picker */}
                  <div className="relative" ref={myDrivePickerRef}>
                    <button
                      type="button"
                      onClick={() => {
                        if (!showMyDrivePicker) {
                          void fetchMyDriveFiles('');
                        }
                        setShowMyDrivePicker((v) => !v);
                      }}
                      className={cn(
                        'flex h-8 w-8 items-center justify-center rounded-full transition-colors',
                        showMyDrivePicker
                          ? 'bg-workspace-accent/15 text-workspace-accent'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      )}
                      title="Select file from My Drive"
                    >
                      <HardDrive size={16} />
                    </button>

                    {showMyDrivePicker && (
                      <div className="absolute bottom-10 left-0 z-50 w-72 rounded-xl border border-border bg-popover shadow-lg">
                        <div className="flex items-center justify-between border-b border-border px-3 py-2">
                          <span className="text-xs font-medium">My Drive</span>
                          {myDrivePath && (
                            <button
                              type="button"
                              className="text-xs text-muted-foreground hover:text-foreground"
                              onClick={() => {
                                const parent = myDrivePath.includes('/')
                                  ? myDrivePath.slice(0, myDrivePath.lastIndexOf('/'))
                                  : '';
                                void fetchMyDriveFiles(parent);
                              }}
                            >
                              ← Back
                            </button>
                          )}
                          <button
                            type="button"
                            className="text-muted-foreground hover:text-foreground"
                            onClick={() => setShowMyDrivePicker(false)}
                          >
                            <X size={14} />
                          </button>
                        </div>

                        <div className="max-h-56 overflow-y-auto py-1">
                          {myDriveLoading && (
                            <div className="flex items-center justify-center py-4">
                              <Loader2 size={16} className="animate-spin text-muted-foreground" />
                            </div>
                          )}
                          {!myDriveLoading && myDriveFiles.length === 0 && (
                            <p className="px-3 py-3 text-center text-xs text-muted-foreground">
                              No files in My Drive
                            </p>
                          )}
                          {!myDriveLoading &&
                            myDriveFiles.map((file) => (
                              <button
                                key={file.path}
                                type="button"
                                className="flex w-full items-center gap-2 px-3 py-2 text-xs hover:bg-muted"
                                onClick={() => {
                                  if (file.type === 'folder') {
                                    void fetchMyDriveFiles(file.path);
                                  } else {
                                    void ingestFromMyDrive(file.path, file.name).catch((err) => {
                                      setImageError(
                                        err instanceof Error ? err.message : `Failed to ingest ${file.name}`,
                                      );
                                    });
                                  }
                                }}
                              >
                                <span className="shrink-0 text-muted-foreground">
                                  {file.type === 'folder' ? '📁' : '📄'}
                                </span>
                                <span className="flex-1 truncate text-left">{file.name}</span>
                                {file.type === 'file' && (
                                  <span className="shrink-0 text-muted-foreground">Add</span>
                                )}
                              </button>
                            ))}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Search the web (globe) */}
                  <button
                    type="button"
                    onClick={() => setSearchEnabled(!searchEnabled)}
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-full transition-colors',
                      searchEnabled
                        ? 'bg-workspace-accent/15 text-workspace-accent'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                    )}
                    title={searchEnabled ? 'Web search enabled' : 'Search the web'}
                  >
                    <Globe size={18} />
                  </button>
                </div>
                
                {/* Send button */}
                <button
                  type="submit"
                  disabled={(!input.trim() && attachedImages.length === 0) || isLoading}
                  className={cn(
                    'flex h-8 w-8 items-center justify-center rounded-full transition-all',
                    (input.trim() || attachedImages.length > 0) && !isLoading
                      ? 'bg-foreground text-background hover:opacity-80'
                      : 'bg-muted text-muted-foreground'
                  )}
                >
                  <ArrowUp size={18} />
                </button>
              </div>
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              AI doesn’t replace your judgment. You’re accountable for its use.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  selectedAgentName,
  logoUrl,
  suggestions,
  onSuggestionClick,
}: {
  selectedAgentName: string;
  logoUrl?: string | null;
  suggestions?: Array<{ label: string; value: string }>;
  onSuggestionClick: (prompt: string) => void;
}) {
  const resolvedLogoUrl = logoUrl ? getLogoUrl(logoUrl) : undefined;
  return (
    <div className="flex h-full flex-col items-center justify-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-workspace-accent-10 overflow-hidden">
        {resolvedLogoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={resolvedLogoUrl}
            alt={selectedAgentName}
            className="h-full w-full object-contain p-1"
          />
        ) : (
          <Bot size={32} className="text-workspace-accent" />
        )}
      </div>
      <p className="mb-8 max-w-md text-center text-muted-foreground">
        Start a conversation with {selectedAgentName}. Ask questions, explore your data, or get
        help with tasks.
      </p>
      {Array.isArray(suggestions) && suggestions.length > 0 && (
        <div className="grid w-full max-w-xl grid-cols-2 gap-3">
          {suggestions.map((suggestion, index) => {
            const isOddLastItem = suggestions.length % 2 === 1 && index === suggestions.length - 1;
            return (
            <button
              key={`${suggestion.label}:${suggestion.value}`}
              onClick={() => onSuggestionClick(suggestion.value)}
              className={cn(
                'glass-card p-4 text-center text-sm transition-all hover:border-primary/30 hover:glow-primary-sm',
                isOddLastItem && 'col-span-2 w-full max-w-[calc(50%-0.375rem)] justify-self-center'
              )}
            >
              {suggestion.label}
            </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function TypingDots() {
  // Discrete caret blink, consistent with login header
  const [on, setOn] = useState(true);
  useEffect(() => {
    const id = setInterval(() => setOn(v => !v), 520);
    return () => clearInterval(id);
  }, []);
  return (
    <span
      className="inline-block align-baseline w-[2px]"
      style={{
        backgroundColor: 'currentColor',
        height: '1em',
        transform: 'translateY(0.08em)',
        opacity: on ? 0.9 : 0,
      }}
    />
  );
}

const MessageBubble = React.memo(function MessageBubble({ 
  message,
  showConnecting,
  showStop,
  onStop,
}: { 
  message: Message; 
  showConnecting: boolean; 
  showStop: boolean; 
  onStop: () => void; 
}) {
  const isUser = message.role === 'user';
  const [showThinking, setShowThinking] = useState(false);
  const [autoCollapsed, setAutoCollapsed] = useState(false);
  const [copiedCodeKey, setCopiedCodeKey] = useState<string | null>(null);
  const wasProcessingRef = useRef(false);
  
  // Get user name and agent info for display
  const user = useAuthStore(state => state.user);
  const agents = useAgentsStore(state => state.agents);
  const agent = agents.find(a => a.id === message.agent);
  
  // Determine sender name
  // BUGFIX: For user-authored messages, prefer the preserved authorName
  // stored with the message. Previously this used the currently logged-in
  // user's name, which caused historical messages to appear as if they were
  // authored by whoever is currently viewing the conversation.
  const senderName = isUser
    ? (message.authorName || user?.name || 'You')
    : (agent?.name || message.agent || 'Assistant');

  // Unwrap JSON-wrapped content if the provider returned {"content": "..."}
  const displayContent = (() => {
    const raw = message.content;
    if (typeof raw !== 'string' || !raw.trim().startsWith('{')) return raw;
    try {
      const obj = JSON.parse(raw);
      if (obj && typeof obj === 'object' && typeof obj.content === 'string') return obj.content;
    } catch {
      // ignore
    }
    return raw;
  })();

  // Parse thinking content from <think>...</think> tags
  const parseThinking = (content: string) => {
    const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/);
    if (thinkMatch) {
      const thinking = thinkMatch[1].trim();
      const response = content.replace(/<think>[\s\S]*?<\/think>/, '').trim();
      return { thinking, response };
    }
    return { thinking: null, response: content };
  };

  const { thinking, response } = isUser ? { thinking: null, response: displayContent } : parseThinking(displayContent);

  // Detect caret placeholder usage in streaming content and strip it for display
  const endsWithCaret = typeof response === 'string' && /▌$/.test(response);
  const responseWithoutCaret = endsWithCaret ? (response as string).slice(0, -1) : response;

  // Still processing if:
  // - we have <think> content and either no visible response yet OR the response ends with the caret token, or
  // - no <think> section but the whole content is just the caret placeholder (initial placeholder)
  const isStillProcessing = !isUser && (
    (thinking !== null ? (!response || endsWithCaret) : (response === '▌'))
  );
  
  // Auto-close thinking 3s after processing finishes
  useEffect(() => {
    if (isStillProcessing) {
      wasProcessingRef.current = true;
    } else if (wasProcessingRef.current && !autoCollapsed) {
      // Processing just finished - auto-collapse after 3s
      const timer = setTimeout(() => {
        setShowThinking(false);
        setAutoCollapsed(true);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [isStillProcessing, autoCollapsed]);
  
  // Format thinking duration
  const formatDuration = (seconds: number) => {
    if (seconds < 1) return '<1s';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  // Show thinking section if we have thinking content OR a finalized duration
  const hasThinkingSection = !isUser && (thinking || (message.thinkingDuration && message.thinkingDuration > 0));
  const handleCopyCode = useCallback(async (code: string, key: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCodeKey(key);
      setTimeout(() => setCopiedCodeKey((current) => (current === key ? null : current)), 1200);
    } catch (error) {
      console.error('Failed to copy code block:', error);
    }
  }, []);

  const markdownComponents = useMemo(
    () => ({
      a: ({
        href,
        children,
        ...props
      }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { children?: React.ReactNode }) => {
        if (!href || !/^https?:\/\//i.test(href)) {
          return <a href={href} {...props}>{children}</a>;
        }
        return (
          <LinkWithPreview href={href} isUserBubble={false}>
            {children ?? href}
          </LinkWithPreview>
        );
      },
      pre: ({
        children,
        ...props
      }: React.HTMLAttributes<HTMLPreElement> & { children?: React.ReactNode }) => {
        const codeChild = Array.isArray(children) ? children[0] : children;
        const className = React.isValidElement(codeChild)
          ? (codeChild.props as { className?: string }).className || ''
          : '';
        const language = className.match(/language-([\w-]+)/)?.[1];
        const rawCodeChildren = React.isValidElement(codeChild)
          ? (codeChild.props as { children?: React.ReactNode }).children
          : undefined;
        const codeContent =
          typeof rawCodeChildren === 'string'
            ? rawCodeChildren
            : Array.isArray(rawCodeChildren)
              ? rawCodeChildren
                .filter((part): part is string => typeof part === 'string')
                .join('')
              : '';
        const copyKey = `${language || 'plain'}:${codeContent}`;

        return (
          <div className="my-5">
            <div className="mb-1 flex items-center justify-between gap-2">
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {language || 'text'}
              </div>
              {codeContent && (
                <button
                  type="button"
                  onClick={() => handleCopyCode(codeContent, copyKey)}
                  className="rounded border border-border/70 px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  title="Copy code"
                >
                  {copiedCodeKey === copyKey ? 'Copied' : 'Copy'}
                </button>
              )}
            </div>
            <pre {...props}>{children}</pre>
          </div>
        );
      },
    }),
    [copiedCodeKey, handleCopyCode]
  );

  return (
    <div className={cn('flex items-start gap-3', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex h-8 w-8 flex-shrink-0 items-center justify-center overflow-hidden',
          isUser
            ? (user?.avatar
                ? 'rounded-full bg-transparent' // Show uploaded/profile avatar
                : 'rounded-full bg-secondary text-secondary-foreground') // Fallback icon bubble
            : agent?.logoUrl
              ? 'rounded-md bg-transparent'  // Agent with logo: square, no bg (transparent)
              : 'rounded-md bg-workspace-accent text-white'  // Agent without logo: square with accent bg
        )}
      >
        {isUser ? (
          user?.avatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={user.avatar} alt={user?.name || 'You'} className="h-full w-full object-cover" />
          ) : (
            <User size={16} />
          )
        ) : agent?.logoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={getLogoUrl(agent.logoUrl)} alt={agent.name} className="h-full w-full object-cover" />
        ) : (
          <Bot size={16} />
        )}
      </div>
      <div className={cn('max-w-[80%] space-y-1', isUser && 'flex flex-col items-end')}>
        {/* Attached images (for user messages) */}
        {isUser && message.images && message.images.length > 0 && (
          <div className={cn('flex flex-wrap gap-2 mb-2', isUser && 'justify-end')}>
            {message.images.map((img, idx) => (
              <Image
                key={idx}
                src={`data:image/jpeg;base64,${img}`}
                alt={`Image ${idx + 1}`}
                width={200}
                height={200}
                className="max-h-48 w-auto rounded-xl border border-border object-contain"
                unoptimized
              />
            ))}
          </div>
        )}
        
        {/* Processing / Processed indicator */}
        {hasThinkingSection && (!isStillProcessing || showThinking) && (
          <div className="w-full">
            <button
              onClick={() => thinking && setShowThinking(!showThinking)}
              className={cn(
                'flex items-center gap-1.5 text-xs text-muted-foreground transition-colors',
                thinking && 'hover:text-foreground cursor-pointer'
              )}
              disabled={!thinking}
            >
              {isStillProcessing ? null : (
                <span className="font-medium">
                  Processed in {formatDuration(message.thinkingDuration || 0)}
                </span>
              )}
              {thinking && (
                <ChevronDown 
                  size={12} 
                  className={cn('transition-transform', showThinking && 'rotate-180')} 
                />
              )}
            </button>
            
            {/* Thinking content - auto-open during processing, auto-close 3s after, user can toggle */}
            {thinking && (showThinking || (isStillProcessing && !autoCollapsed)) && (
              <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-border/50 bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
                <p className="whitespace-pre-wrap leading-relaxed">{thinking}</p>
              </div>
            )}
          </div>
        )}
        
        {/* Main response bubble */}
        <div
          className={cn(
            'rounded-2xl px-4 py-3 text-sm',
            isUser ? 'bg-workspace-accent text-white' : 'bg-muted max-w-none',
            !isUser &&
              '[&_p]:my-2 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-6 [&_li]:my-1 [&_li]:pt-0.5 [&_li]:leading-relaxed [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-sm [&_code]:bg-background/50 [&_code]:px-1 [&_code]:rounded [&_code]:font-mono [&_pre]:my-0 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:border [&_pre]:border-border/70 [&_pre]:bg-background/80 [&_pre]:p-3 [&_pre]:text-xs [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:rounded-none [&_pre_code]:text-inherit'
          )}
        >
          {/* Sender name inside bubble (WhatsApp-style) */}
          <div className={cn(
            'text-xs font-bold mb-1.5 pb-1',
            isUser 
              ? 'text-right text-white border-b border-white/20' 
              : 'text-left text-workspace-accent border-b border-border'
          )}>
            {senderName}
          </div>
          
          {isUser ? (
            <p className="whitespace-pre-wrap text-right">
              {(response as string).match(URL_REGEX) ? linkifyText(response as string, true) : response}
            </p>
          ) : isStillProcessing ? (
            <div className="flex items-baseline gap-1">
              {responseWithoutCaret && (
                <div className="max-w-full [&>*]:m-0">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                    {responseWithoutCaret}
                  </ReactMarkdown>
                </div>
              )}
              <TypingDots />
              {!responseWithoutCaret && showConnecting && (
                <span className="ml-2 text-xs text-muted-foreground">Processing…</span>
              )}
              {showStop && (
                <button
                  className="ml-2 rounded px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-muted"
                  onClick={(e) => { e.preventDefault(); onStop(); }}
                  title="Stop generation"
                >
                  Stop
                </button>
              )}
            </div>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {responseWithoutCaret}
            </ReactMarkdown>
          )}
        </div>

        {/* Source pills — shown when RAG context was used */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5 px-1">
            {message.sources.map((src) => (
              <span
                key={src}
                className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-background px-2.5 py-0.5 text-xs text-muted-foreground"
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                {src}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
});

function getMockResponse(userMessage: string, agent: AgentType): string {
  const responses: Record<string, string[]> = {
    abi: [
      "As your supervisor agent, I've analyzed the full context of your request...",
      "Let me orchestrate the right resources to help with this...",
    ],
    aia: [
      "I've analyzed your request. Here's what I found based on your personal knowledge graph...",
      'Let me help you with that. Based on your recent activity and preferences...',
    ],
    bob: [
      "From a business perspective, here's my analysis of this situation...",
      "I've examined the organizational data relevant to your query...",
    ],
    system: [
      'Processing your request through the NEXUS system...',
      "I've queried the platform APIs and here's the result...",
    ],
  };

  const fallback = ["I'm processing your request..."];
  const agentResponses = responses[agent] || fallback;
  const prefix = agentResponses[Math.floor(Math.random() * agentResponses.length)];

  return `${prefix}\n\nRegarding "${userMessage.slice(0, 50)}${userMessage.length > 50 ? '...' : ''}":\n\nCould not reach the AI provider. Please check that Ollama is running or configure a provider in Settings.`;
}
