'use client';

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Send, Plus, Bot, User, AlertCircle, Brain, ChevronDown, X, Globe, ArrowUp, Download } from 'lucide-react';
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

const API_BASE = getApiUrl();

// Helper to get logo URL (prefix relative URLs with API base)
const getLogoUrl = (url: string | null): string | undefined => {
  if (!url) return undefined;
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  return `${API_BASE}${url}`; // Relative URL -> add API base
};

// Max image size for uploads (5MB)
const MAX_IMAGE_SIZE = 5 * 1024 * 1024;
const SUPPORTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];

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
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const {
    activeConversationId,
    selectedAgent,
    createConversation,
    addMessage,
    updateLastMessage,
    getWorkspaceConversations,
    currentWorkspaceId,
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && attachedImages.length === 0) || isLoading) return;

    let conversationId = activeConversationId;

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
      
      // Get current conversation with fresh state (including the just-added user message)
      // Using getState() to get the latest state after addMessage() was called
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

        try {
          const controller = new AbortController();
          streamControllerRef.current = controller;
          const response = await fetch(`${API_BASE}/api/chat/stream`, {
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
            window.location.href = '/login';
            return;
          }
          throw new Error(`API error: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';       // Full raw content (including <think> tags)
        let thinkingContent = '';   // Accumulated thinking text
        let responseContent = '';   // Accumulated response text
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
                    updateLastMessage(conversationId!, '🌐 Searching the web...');
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
                      // Build content with thinking - MessageBubble will render the collapsible
                      const assembled = `<think>${thinkingContent}</think>`;
                      updateLastMessage(conversationId!, assembled);
                      continue;
                    }
                    
                    if (token.includes('</think>')) {
                      isInThinking = false;
                      // Close thinking, show response placeholder
                      const assembled = `<think>${thinkingContent}</think>\n\n▌`;
                      updateLastMessage(conversationId!, assembled);
                      continue;
                    }
                    
                    if (isInThinking) {
                      // Stream thinking content live
                      thinkingContent += token;
                      const assembled = `<think>${thinkingContent}</think>`;
                      updateLastMessage(conversationId!, assembled);
                      continue;
                    }
                    
                    // Regular response content
                    responseContent += token;
                    const assembled = thinkingContent 
                      ? `<think>${thinkingContent}</think>\n\n${responseContent}▌`
                      : `${responseContent}▌`;
                    updateLastMessage(conversationId!, assembled);
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
        const finalContent = thinkingContent 
          ? `<think>${thinkingContent}</think>\n\n${responseContent}`
          : responseContent;
        updateLastMessage(conversationId!, finalContent, thinkingDuration);
      } catch (streamError) {
        // Gracefully handle user-initiated aborts
        if ((streamError as any)?.name === 'AbortError') {
          const finalContent = thinkingContent
            ? `<think>${thinkingContent}</think>\n\n${responseContent}`
            : responseContent;
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
        
        const response = await fetch(`${API_BASE}/api/chat/complete`, {
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
        });
      }
    } catch (error) {
      console.error('Chat API error:', error);
      
      // Check if it's an Ollama connection error
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      const isOllamaError = errorMessage.includes('Ollama') || errorMessage.includes('11434') || errorMessage.includes('Could not reach');
      
      if (isOllamaError) {
        // If we added a placeholder message, update it with error instead of adding new one
        if (conversationId && isStreaming) {
          updateLastMessage(conversationId, `❌ Ollama is not running or not reachable.\n\nClick below to start it automatically.`);
        }
        
        // Show modal to user
        if (confirm('❌ Ollama is not running.\n\nWould you like to start Ollama and pull the required model?\n\n(This may take a few minutes on first run)')) {
          try {
            // Update the message to show we're starting
            if (conversationId) {
              updateLastMessage(conversationId, '🔄 Starting Ollama and pulling model...\n\n⏳ This may take 1-2 minutes on first run.\n\nPlease wait...');
            }
            
            setIsLoading(true);
            
            // Try to ensure Ollama is ready (will auto-start + pull model)
            const ensureResponse = await fetch(`${API_BASE}/api/ollama/ensure-ready`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
            });
            
            const ensureData = await ensureResponse.json();
            
            if (ensureData.ready) {
              // Remove the loading message before retry
              if (conversationId) {
                useWorkspaceStore.setState(state => ({
                  conversations: state.conversations.map(c => 
                    c.id === conversationId 
                      ? { ...c, messages: c.messages.slice(0, -1) }
                      : c
                  )
                }));
              }
              
              // Retry the message automatically
              alert('✅ Ollama is ready! Retrying your message...');
              // Reconstruct and resubmit
              await handleSubmit(new Event('submit') as any);
              return;
            } else {
              // Update message with error
              if (conversationId) {
                updateLastMessage(conversationId, `⚠️ Could not start Ollama: ${ensureData.error || 'Unknown error'}\n\nPlease start Ollama manually and try again.`);
              }
            }
          } catch (startError) {
            console.error('Failed to start Ollama:', startError);
            if (conversationId) {
              updateLastMessage(conversationId, '⚠️ Failed to start Ollama automatically.\n\nPlease start it manually:\n• macOS: Open Ollama.app\n• Linux: Run `ollama serve`\n\nThen try your message again.');
            }
          } finally {
            setIsLoading(false);
          }
        } else {
          // User cancelled - remove the error message
          if (conversationId) {
            useWorkspaceStore.setState(state => ({
              conversations: state.conversations.map(c => 
                c.id === conversationId 
                  ? { ...c, messages: c.messages.slice(0, -1) }
                  : c
              )
            }));
          }
        }
      } else {
        // For other errors, update the placeholder if it exists, otherwise add new message
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
        `${API_BASE}/api/chat/conversations/${activeConversation.id}/export?format=txt`
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
          <EmptyState onSuggestionClick={(prompt) => setInput(prompt)} />
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

function EmptyState({ onSuggestionClick }: { onSuggestionClick: (prompt: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-workspace-accent-10">
        <Bot size={32} className="text-workspace-accent" />
      </div>
      <h2 className="mb-2 text-xl font-semibold text-gradient">Welcome to NEXUS Chat</h2>
      <p className="mb-8 max-w-md text-center text-muted-foreground">
        Start a conversation with an ABI-powered agent. Ask questions, explore your data, or get
        help with tasks.
      </p>
      <div className="grid max-w-xl gap-3 sm:grid-cols-2">
        {[
          'What can you help me with?',
          'Show me my recent ontology changes',
          'Search for entities related to...',
          'Help me create a new workflow',
        ].map((prompt) => (
          <button
            key={prompt}
            onClick={() => onSuggestionClick(prompt)}
            className="glass-card p-4 text-left text-sm transition-all hover:border-primary/30 hover:glow-primary-sm"
          >
            {prompt}
          </button>
        ))}
      </div>
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

  const { thinking, response } = isUser ? { thinking: null, response: message.content } : parseThinking(message.content);

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
            isUser ? 'bg-workspace-accent text-white' : 'bg-muted prose prose-sm dark:prose-invert max-w-none',
            !isUser && '[&_p]:my-1 [&_ul]:my-2 [&_ol]:my-2 [&_li]:my-0.5 [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-sm [&_code]:bg-background/50 [&_code]:px-1 [&_code]:rounded'
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
            <p className="whitespace-pre-wrap text-right">{response}</p>
          ) : isStillProcessing ? (
            <div className="flex items-baseline gap-1">
              {responseWithoutCaret && (
                <div className="max-w-full [&>*]:m-0">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{responseWithoutCaret}</ReactMarkdown>
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
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{responseWithoutCaret}</ReactMarkdown>
          )}
        </div>
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
