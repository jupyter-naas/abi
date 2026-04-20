'use client';

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Send, Plus, Bot, User, AlertCircle, Brain, ChevronDown, X, Globe, ArrowUp, Download, ExternalLink, Mic, Check, Loader2 } from 'lucide-react';
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
  const [searchEnabled, setSearchEnabled] = useState(false); // Force web search
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Voice capture state
  const [voiceMode, setVoiceMode] = useState<'idle' | 'recording' | 'transcribing'>('idle');
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const recordingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  const { startTyping, stopTyping, onMessage } = useWebSocket();

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

  // Handle image file selection
  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    
    setImageError(null);
    const newImages: string[] = [];
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      
      // Validate file type
      if (!SUPPORTED_IMAGE_TYPES.includes(file.type)) {
        setImageError(`Unsupported file type: ${file.type}. Use JPEG, PNG, GIF, or WebP.`);
        continue;
      }
      
      // Validate file size
      if (file.size > MAX_IMAGE_SIZE) {
        setImageError(`File too large: ${file.name}. Max size is 5MB.`);
        continue;
      }
      
      // Convert to base64
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
  };

  const removeImage = (index: number) => {
    setAttachedImages(attachedImages.filter((_, i) => i !== index));
    setImageError(null);
  };

  // ---------- Voice capture ----------

  const stopVoiceStream = useCallback(() => {
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        // ignore
      }
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current) {
      void audioContextRef.current.close().catch(() => undefined);
      audioContextRef.current = null;
    }
    analyserRef.current = null;
  }, []);

  const startVoiceRecording = async () => {
    setVoiceError(null);
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setVoiceError('Microphone is not supported in this browser.');
      return;
    }
    try {
      // Browser handles the permission prompt. If denied, getUserMedia throws.
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      // Pick a supported mime type (Chrome/Firefox → webm; Safari → mp4)
      const mimeCandidates = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
        'audio/ogg;codecs=opus',
      ];
      const mimeType = mimeCandidates.find(
        (m) => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(m)
      );

      const recorder = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : undefined
      );
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.start(200);

      // Analyser for live waveform visualization
      try {
        const AudioCtx =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (AudioCtx) {
          const ctx = new AudioCtx();
          audioContextRef.current = ctx;
          const source = ctx.createMediaStreamSource(stream);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 512;
          source.connect(analyser);
          analyserRef.current = analyser;
        }
      } catch {
        // Waveform is non-critical - ignore failures
      }

      setRecordingSeconds(0);
      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds((s) => s + 1);
      }, 1000);

      setVoiceMode('recording');
    } catch (err) {
      const name = (err as { name?: string })?.name;
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setVoiceError('Microphone access was denied. Please allow it in your browser settings.');
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        setVoiceError('No microphone was found on this device.');
      } else {
        const message = err instanceof Error ? err.message : 'Unable to access microphone';
        setVoiceError(message);
      }
      stopVoiceStream();
      setVoiceMode('idle');
    }
  };

  const cancelVoiceRecording = useCallback(() => {
    stopVoiceStream();
    audioChunksRef.current = [];
    setRecordingSeconds(0);
    setVoiceMode('idle');
    setVoiceError(null);
  }, [stopVoiceStream]);

  const confirmVoiceRecording = useCallback(async () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder) {
      cancelVoiceRecording();
      return;
    }

    setVoiceMode('transcribing');

    const blob: Blob = await new Promise((resolve) => {
      const mimeType = recorder.mimeType || 'audio/webm';
      if (recorder.state === 'inactive') {
        resolve(new Blob(audioChunksRef.current, { type: mimeType }));
        return;
      }
      recorder.onstop = () => {
        resolve(new Blob(audioChunksRef.current, { type: mimeType }));
      };
      try {
        recorder.stop();
      } catch {
        resolve(new Blob(audioChunksRef.current, { type: mimeType }));
      }
    });

    // Release the mic once we have the audio
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    if (audioContextRef.current) {
      void audioContextRef.current.close().catch(() => undefined);
      audioContextRef.current = null;
    }
    analyserRef.current = null;

    if (blob.size === 0) {
      setVoiceError('No audio was captured. Please try again.');
      setVoiceMode('idle');
      return;
    }

    try {
      const extension = blob.type.includes('mp4')
        ? 'mp4'
        : blob.type.includes('ogg')
          ? 'ogg'
          : 'webm';
      const file = new File([blob], `recording.${extension}`, { type: blob.type });

      const formData = new FormData();
      formData.append('audio', file);
      const currentConversationId = useWorkspaceStore.getState().activeConversationId;
      if (currentConversationId) {
        formData.append('conversation_id', currentConversationId);
      }

      const response = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || `Transcription failed (${response.status})`);
      }

      const { text, conversation_id: echoedConversationId } =
        (await response.json()) as { text?: string; conversation_id?: string | null };
      const transcript = (text || '').trim();

      setVoiceMode('idle');
      setRecordingSeconds(0);
      audioChunksRef.current = [];

      if (!transcript) {
        setVoiceError('No speech was detected. Please try again.');
        return;
      }

      const preservedConversationId = echoedConversationId ?? currentConversationId;
      if (
        preservedConversationId &&
        useWorkspaceStore.getState().activeConversationId !== preservedConversationId
      ) {
        useWorkspaceStore.getState().setActiveConversation(preservedConversationId);
      }

      // On validate: send the transcript directly as a chat message.
      // If the user had already typed something, prepend it so nothing is lost.
      const existing = textareaRef.current?.value ?? '';
      const combined = existing.trim()
        ? `${existing.trim()} ${transcript}`
        : transcript;
      const selectedAgentAtSend = useWorkspaceStore.getState().selectedAgent;

      handleInputChange('');
      await handleSubmit(undefined, combined, selectedAgentAtSend);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Transcription failed';
      setVoiceError(message);
      setVoiceMode('idle');
      setRecordingSeconds(0);
      audioChunksRef.current = [];
    }
  }, [cancelVoiceRecording]);

  // Keyboard shortcut: Ctrl+M validates the current voice recording
  useEffect(() => {
    if (voiceMode !== 'recording') return;
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'm') {
        e.preventDefault();
        void confirmVoiceRecording();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        cancelVoiceRecording();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [voiceMode, confirmVoiceRecording, cancelVoiceRecording]);

  // Cleanup mic resources if the component unmounts while recording
  useEffect(() => {
    return () => {
      stopVoiceStream();
    };
  }, [stopVoiceStream]);

  const handleSubmit = async (
    e?: React.FormEvent,
    messageOverride?: string,
    agentOverride?: string
  ) => {
    e?.preventDefault();
    const sourceText = messageOverride !== undefined ? messageOverride : input;
    if ((!sourceText.trim() && attachedImages.length === 0) || isLoading) return;
    const effectiveAgent = agentOverride ?? selectedAgent;

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
      content: sourceText.trim() || (attachedImages.length > 0 ? 'What is in this image?' : ''),
      images: currentImages.length > 0 ? currentImages : undefined,
    });

    const userMessage = sourceText.trim() || (currentImages.length > 0 ? 'What is in this image?' : '');
    // Only clear the input field if the message came from the input
    if (messageOverride === undefined) {
      handleInputChange('');
    } else {
      setInput('');
    }
    setAttachedImages([]); // Clear attached images after adding to message
    setImageError(null);
    setSearchEnabled(false); // Reset search toggle after sending
    setIsLoading(true);

    try {
      // Get provider for current agent
      const provider = getProviderForAgent(effectiveAgent);
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
      const agentData = getAgent(effectiveAgent);
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
          agent: effectiveAgent,
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
            agent: effectiveAgent,
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
        updateLastMessage(conversationId!, finalContent, thinkingDuration);
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
          if (conversationId) updateLastMessage(conversationId, finalContent);
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
            agent: effectiveAgent,
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
          agent: effectiveAgent,
          thinkingDuration,
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
              agent: effectiveAgent,
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
            
            {/* Voice error banner */}
            {voiceError && (
              <div className="mb-2 flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
                <AlertCircle size={14} />
                {voiceError}
                <button
                  type="button"
                  onClick={() => setVoiceError(null)}
                  className="ml-auto rounded p-0.5 hover:bg-destructive/10"
                  aria-label="Dismiss"
                >
                  <X size={12} />
                </button>
              </div>
            )}

            {voiceMode === 'idle' ? (
            <div className="rounded-2xl border border-border/50 bg-card">
              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/gif,image/webp"
                multiple
                className="hidden"
                onChange={handleImageSelect}
              />
              
              {/* Row 1: Textarea */}
              <div className="px-4 pt-3 pb-1">
                <textarea
                  ref={textareaRef}
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
                    title="Attach file"
                  >
                    <Plus size={20} />
                  </button>
                  
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
                
                <div className="flex items-center gap-1">
                  {/* Voice capture (mic) */}
                  <button
                    type="button"
                    onClick={startVoiceRecording}
                    disabled={isLoading}
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-full transition-colors',
                      'text-muted-foreground hover:bg-muted hover:text-foreground',
                      isLoading && 'cursor-not-allowed opacity-50'
                    )}
                    title="Record voice message"
                    aria-label="Record voice message"
                  >
                    <Mic size={18} />
                  </button>

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
            </div>
            ) : (
              <VoiceRecorderBar
                mode={voiceMode}
                seconds={recordingSeconds}
                analyser={analyserRef.current}
                onCancel={cancelVoiceRecording}
                onConfirm={() => void confirmVoiceRecording()}
              />
            )}
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
      </div>
    </div>
  );
});

/**
 * Voice recorder UI that replaces the chat composer while the user records
 * or while audio is being transcribed. Mirrors the pill-shaped bar from the
 * design reference: left-aligned timer, live waveform in the middle, and
 * cancel / validate controls on the right.
 */
function VoiceRecorderBar({
  mode,
  seconds,
  analyser,
  onCancel,
  onConfirm,
}: {
  mode: 'recording' | 'transcribing';
  seconds: number;
  analyser: AnalyserNode | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Rolling history of amplitudes (oldest -> newest, left -> right).
  // Each entry is in [0, 1]. Scrolled at a fixed cadence for steady motion.
  const historyRef = useRef<number[]>([]);
  const lastSampleAtRef = useRef(0);

  // Design constants matching the reference (dashed grey rail + black bars).
  const SLOT_WIDTH = 3;        // px per history slot (bar + gap)
  const BAR_WIDTH = 1.4;       // px thickness of the black bars
  const SAMPLE_INTERVAL_MS = 45; // timeline scroll speed
  const SILENCE_FLOOR = 0.06;  // below this, only the dashed rail shows
  const DASH_STEP = 6;         // px between dashed baseline dots
  const DASH_WIDTH = 2;        // px length of each dot

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let rafId = 0;
    const bufferLength = analyser?.fftSize ?? 512;
    const dataArray = new Uint8Array(bufferLength);

    const draw = (now: number) => {
      rafId = requestAnimationFrame(draw);

      const width = canvas.clientWidth || canvas.width;
      const height = canvas.clientHeight || canvas.height;
      ctx.clearRect(0, 0, width, height);

      const midY = height / 2;
      const maxBarHeight = height * 0.85;

      // --- 1. Measure current mic level (RMS) as a new history sample ---
      let currentLevel = 0;
      if (analyser && mode === 'recording') {
        analyser.getByteTimeDomainData(dataArray);
        let sumSq = 0;
        for (let i = 0; i < dataArray.length; i++) {
          const v = (dataArray[i] - 128) / 128;
          sumSq += v * v;
        }
        const rms = Math.sqrt(sumSq / dataArray.length);
        // Shape the response: gentle lift for soft voice, clamp loud peaks.
        currentLevel = Math.min(1, rms * 3.0);
      }

      // --- 2. Advance the timeline at a fixed cadence (independent of FPS) ---
      const maxSlots = Math.max(8, Math.ceil(width / SLOT_WIDTH));
      if (lastSampleAtRef.current === 0) {
        lastSampleAtRef.current = now;
        historyRef.current = new Array(maxSlots).fill(0);
      }
      while (now - lastSampleAtRef.current >= SAMPLE_INTERVAL_MS) {
        historyRef.current.push(currentLevel);
        if (historyRef.current.length > maxSlots) {
          historyRef.current.splice(0, historyRef.current.length - maxSlots);
        }
        lastSampleAtRef.current += SAMPLE_INTERVAL_MS;
      }
      // Pad if the history is shorter than the canvas (initial frames, resize).
      if (historyRef.current.length < maxSlots) {
        const pad = new Array(maxSlots - historyRef.current.length).fill(0);
        historyRef.current = pad.concat(historyRef.current);
      }

      // --- 3. Draw the dashed grey baseline across the full width ---
      ctx.fillStyle = 'rgba(0, 0, 0, 0.22)';
      for (let x = 0; x <= width - DASH_WIDTH; x += DASH_STEP) {
        ctx.fillRect(x, midY - 0.5, DASH_WIDTH, 1);
      }

      // --- 4. Overlay black oscillation bars for slots with audible voice ---
      ctx.fillStyle = mode === 'transcribing' ? 'rgba(0, 0, 0, 0.45)' : '#111';
      const history = historyRef.current;
      for (let i = 0; i < maxSlots; i++) {
        const level = history[i] ?? 0;
        if (level < SILENCE_FLOOR) continue;

        // Map i=0 -> left edge (oldest), i=maxSlots-1 -> right edge (now)
        const x = i * SLOT_WIDTH + (SLOT_WIDTH - BAR_WIDTH) / 2;
        const barHeight = Math.max(2, level * maxBarHeight);
        ctx.fillRect(x, midY - barHeight / 2, BAR_WIDTH, barHeight);
      }
    };

    rafId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, analyser]);

  // Keep the canvas backing buffer in sync with its CSS size (HiDPI support)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);
      }
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);

  const formatDuration = (total: number) => {
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const isTranscribing = mode === 'transcribing';

  return (
    <div className="flex items-center gap-2 rounded-full border border-border/50 bg-card px-3 py-2">
      {/* Left: timer / status */}
      <div className="flex min-w-[70px] items-center gap-2 pl-1 pr-2 text-xs font-medium text-muted-foreground tabular-nums">
        {isTranscribing ? (
          <>
            <Loader2 size={14} className="animate-spin text-workspace-accent" />
            <span>Transcribing…</span>
          </>
        ) : (
          <>
            <span
              className="h-2 w-2 animate-pulse rounded-full bg-destructive"
              aria-hidden="true"
            />
            <span>{formatDuration(seconds)}</span>
          </>
        )}
      </div>

      {/* Middle: waveform */}
      <div
        className={cn(
          'relative flex h-8 flex-1 items-center',
          isTranscribing ? 'text-muted-foreground/40' : 'text-foreground'
        )}
      >
        <canvas ref={canvasRef} className="h-full w-full" />
      </div>

      {/* Right: cancel & validate */}
      <div className="flex items-center gap-1 pr-1">
        <button
          type="button"
          onClick={onCancel}
          disabled={isTranscribing}
          className={cn(
            'flex h-8 w-8 items-center justify-center rounded-full transition-colors',
            'text-muted-foreground hover:bg-muted hover:text-foreground',
            isTranscribing && 'cursor-not-allowed opacity-50'
          )}
          title="Cancel recording (Esc)"
          aria-label="Cancel recording"
        >
          <X size={18} />
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={isTranscribing}
          className={cn(
            'flex h-8 w-8 items-center justify-center rounded-full transition-all',
            isTranscribing
              ? 'bg-muted text-muted-foreground'
              : 'bg-foreground text-background hover:opacity-80'
          )}
          title="Validate (Ctrl + M)"
          aria-label="Validate recording"
        >
          {isTranscribing ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Check size={18} />
          )}
        </button>
      </div>
    </div>
  );
}

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
