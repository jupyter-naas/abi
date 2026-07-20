'use client';

import React, { useState, useRef, useEffect, useMemo, useCallback, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
import { Send, Plus, Bot, User, AlertCircle, Brain, ChevronDown, X, ArrowUp, Download, ExternalLink, HardDrive, RefreshCw, Mic, Check, Loader2, Wrench, Copy, FileText, ThumbsUp, ThumbsDown } from 'lucide-react';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, type AgentType, type Message, type MessageFeedback, type MessageFeedbackDetails, type SidebarSection, type ToolCall } from '@/stores/workspace';
import { useIntegrationsStore } from '@/stores/integrations';
import { useAgentsStore } from '@/stores/agents';
import { useSkillsStore, type Skill, type SkillScope } from '@/stores/skills';
import { useSecretsStore } from '@/stores/secrets';
import { useAuthStore, authFetch } from '@/stores/auth';
import { useWebSocket } from '@/contexts/websocket-context';
import { useTenant } from '@/contexts/tenant-context';
import { AgentSelector, ModelSelector } from './agent-selector';
import { TypingIndicator } from '@/components/typing-indicator';
import { PdfViewer } from '@/components/files/pdf-viewer';

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

// ---------- Skills slash commands ----------

// "/command optional args" at the start of a message
const SLASH_COMMAND_RE = /^\/([a-zA-Z0-9][a-zA-Z0-9_-]*)\s*([\s\S]*)$/;

const BUILTIN_SLASH_COMMANDS = [
  {
    slug: 'skills',
    name: 'List skills',
    description: 'Show all skills available in this workspace',
  },
  {
    slug: 'create-skill',
    name: 'Create a skill',
    description: 'Ask the agent to draft a reusable skill prompt',
  },
];

function formatSkillListing(skills: Skill[]): string {
  const enabled = skills.filter((s) => s.enabled);
  if (enabled.length === 0) {
    return 'No skills yet. Type `/create-skill <what the skill should do>` and I will draft one for you.';
  }
  const lines = [...enabled]
    .sort((a, b) => a.slug.localeCompare(b.slug))
    .map(
      (s) =>
        `- \`/${s.slug}\` — **${s.name}**${s.description ? `: ${s.description}` : ''} _(${s.scope})_`
    );
  return [
    `**Available skills (${enabled.length})**`,
    '',
    ...lines,
    '',
    'Run one with `/<slug> [extra instructions]`, or `/create-skill <description>` to create a new one.',
  ].join('\n');
}

function buildCreateSkillInstruction(description: string): string {
  const goal =
    description || 'Not provided — infer the most useful skill from this conversation so far.';
  return [
    'You are helping the user create a reusable "skill": a saved prompt they can re-run in this chat with a /slash command.',
    '',
    `The user's description of the skill: ${goal}`,
    '',
    'Design the best possible skill. Reply with:',
    '1. One short paragraph explaining what the skill does and when to use it.',
    '2. A fenced code block with language `skill` containing ONLY a valid JSON object with exactly these fields:',
    '   - "name": short human-readable name',
    '   - "slug": short kebab-case command (lowercase letters, digits, hyphens)',
    '   - "description": one sentence describing the skill',
    '   - "prompt": the full reusable prompt — self-contained, with a clear task, constraints, and expected output format',
    '',
    'The user will review the draft and save it with one click.',
  ].join('\n');
}

/** Card rendered for ```skill fenced blocks in assistant messages: shows the
 *  agent's skill draft with a scope picker and a one-click save. */
function SkillDraftCard({ raw }: { raw: string }) {
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const createSkill = useSkillsStore((s) => s.createSkill);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [scope, setScope] = useState<SkillScope>('user');
  const [showPrompt, setShowPrompt] = useState(false);

  const draft = useMemo(() => {
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed.name === 'string' && typeof parsed.prompt === 'string') {
        return {
          name: parsed.name as string,
          slug: typeof parsed.slug === 'string' ? (parsed.slug as string) : undefined,
          description:
            typeof parsed.description === 'string' ? (parsed.description as string) : undefined,
          prompt: parsed.prompt as string,
        };
      }
    } catch {
      // Partial JSON while the message is still streaming
    }
    return null;
  }, [raw]);

  const handleSave = async () => {
    if (!currentWorkspaceId || !draft) return;
    setSaveState('saving');
    setSaveError(null);
    try {
      await createSkill(currentWorkspaceId, {
        name: draft.name,
        slug: draft.slug,
        description: draft.description,
        prompt: draft.prompt,
        scope,
      });
      setSaveState('saved');
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save skill');
      setSaveState('error');
    }
  };

  if (!draft) {
    return (
      <div className="my-3 flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <Loader2 size={12} className="animate-spin" />
        Drafting skill…
      </div>
    );
  }

  return (
    <div className="my-3 rounded-lg border border-border bg-muted/30 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">{draft.name}</p>
          {draft.slug && (
            <p className="font-mono text-xs text-workspace-accent">/{draft.slug}</p>
          )}
          {draft.description && (
            <p className="mt-1 text-xs text-muted-foreground">{draft.description}</p>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={() => setShowPrompt(!showPrompt)}
        className="mt-2 text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
      >
        {showPrompt ? 'Hide prompt' : 'Show prompt'}
      </button>
      {showPrompt && (
        <pre className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-background p-2 text-xs text-muted-foreground">
          {draft.prompt}
        </pre>
      )}

      <div className="mt-3 flex items-center gap-2">
        <select
          value={scope}
          onChange={(e) => setScope(e.target.value as SkillScope)}
          disabled={saveState === 'saved' || saveState === 'saving'}
          className="rounded-md border border-border bg-background px-2 py-1 text-xs"
        >
          <option value="user">Private (only me)</option>
          <option value="workspace">Workspace</option>
          <option value="organization">Organization</option>
        </select>
        <button
          type="button"
          onClick={handleSave}
          disabled={saveState === 'saved' || saveState === 'saving'}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors',
            saveState === 'saved'
              ? 'bg-workspace-accent/15 text-workspace-accent'
              : 'bg-workspace-accent text-white hover:opacity-90'
          )}
        >
          {saveState === 'saving' && <Loader2 size={12} className="animate-spin" />}
          {saveState === 'saved' && <Check size={12} />}
          {saveState === 'saved'
            ? `Saved — use /${draft.slug ?? ''}`
            : saveState === 'saving'
              ? 'Saving…'
              : 'Save skill'}
        </button>
      </div>
      {saveError && <p className="mt-2 text-xs text-destructive">{saveError}</p>}
    </div>
  );
}

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

/** Wrap bare URLs (not already in [text](url) syntax) as [domain](url) markdown links. */
function transformBareUrls(content: string): string {
  return content.replace(
    /(?<!\]\()https?:\/\/[^\s<>\]\)]+?(?=[\s<>\]\)]|$)/g,
    (url) => {
      try {
        const h = new URL(url).hostname;
        const domain = h.startsWith('www.') ? h.slice(4) : h;
        return `[${domain}](${url})`;
      } catch {
        return url;
      }
    }
  );
}

/**
 * Strip a trailing "Sources" block from message content so it isn't rendered
 * inline — the sources are shown in the dedicated collapsible panel instead.
 * Handles variants: "Sources", "**Sources**", "## Sources", etc.
 * Also removes trailing bare URL lines (e.g. a lone https://… at the end).
 */
function stripTrailingSources(content: string): string {
  // Remove "Sources" heading + everything after it when at the end of the text
  let result = content.replace(
    /\n{1,2}(?:#{1,3}\s*)?(?:\*{1,2})?Sources(?:\*{1,2})?:?\s*\n[\s\S]*$/i,
    ''
  );
  // Remove trailing lines that are only a bare URL
  result = result.replace(/(\n+https?:\/\/\S+)+\s*$/, '');
  return result.trimEnd();
}

/** Extract unique HTTP(S) URLs from message content (markdown links + bare URLs). */
function extractUrlsFromContent(content: string): string[] {
  if (!content) return [];
  const urls = new Set<string>();
  const mdLinkRe = /\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g;
  let m: RegExpExecArray | null;
  while ((m = mdLinkRe.exec(content)) !== null) urls.add(m[2]);
  const stripped = content.replace(/\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g, '');
  const bareRe = /https?:\/\/[^\s<>\]\)]+?(?=[\s<>\]\)]|$)/g;
  while ((m = bareRe.exec(stripped)) !== null) urls.add(m[0]);
  return Array.from(urls);
}

const LOGIN_REQUIRED_RE = /(?:^|\.)linkedin\.com$/i;

function isLoginRequiredDomain(url: string): boolean {
  try {
    return LOGIN_REQUIRED_RE.test(new URL(url).hostname);
  } catch {
    return false;
  }
}

// Paths and extensions that reliably serve binary/download content.
// Iframing these URLs triggers a browser download dialog, so we skip the probe.
const FILE_PATH_RE = /\/asset\/[^/]+\/object\b|\/download\/|\/export\/|\/file\/[^/?#]+(?:[?#]|$)/i;
const FILE_EXT_RE = /\.(pdf|xlsx?|docx?|pptx?|zip|tar\.gz|gz|csv|tsv|mp4|mp3|wav|png|jpe?g|gif|svg|webp|ico|json|xml|ttl|rdf|owl)(?:[?#]|$)/i;

function isLikelyFileUrl(url: string): boolean {
  try {
    const { pathname } = new URL(url);
    return FILE_PATH_RE.test(url) || FILE_EXT_RE.test(pathname);
  } catch {
    return false;
  }
}

function isPdfUrl(url: string): boolean {
  try {
    const { pathname } = new URL(url);
    return /\.pdf$/i.test(pathname.split('?')[0]);
  } catch {
    return /\.pdf$/i.test(url.split('?')[0]);
  }
}

// Module-level cache so URL validity is checked at most twice (CORS GET → no-cors HEAD)
// and the result is reused across re-renders and component instances.
const urlValidityCache = new Map<string, boolean>();

/** Right-side preview panel.
 *  Loads the URL directly in an iframe.
 *  If the site blocks embedding (empty contentDocument on load), closes the
 *  panel and opens the URL in a new browser tab instead.
 */
function PreviewPanel({ url, onClose, width }: { url: string; onClose: () => void; width: number }) {
  const [reloadKey, setReloadKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const domain = (() => { try { return new URL(url).hostname; } catch { return url; } })();

  useEffect(() => {
    setIsLoading(true);
    setReloadKey((k) => k + 1);
  }, [url]);

  const handleLoad = useCallback(() => {
    try {
      const doc = iframeRef.current?.contentDocument;
      // Accessible + empty body = browser blocked the embed (X-Frame-Options / CSP).
      // A cross-origin page that loaded successfully throws SecurityError here instead.
      if (doc && (!doc.body || doc.body.innerHTML === '')) {
        onClose();
        window.open(url, '_blank', 'noopener,noreferrer');
        return;
      }
    } catch {
      // SecurityError = cross-origin page loaded fine — keep the panel open.
    }
    setIsLoading(false);
  }, [url, onClose]);

  const handleReload = () => {
    setIsLoading(true);
    setReloadKey((k) => k + 1);
  };

  return (
    <div className="flex flex-col border-border bg-background" style={{ width, minWidth: 280, maxWidth: 900 }}>
      {/* Header */}
      <div className="flex items-center gap-1.5 border-b border-border px-3 py-2">
        <span className="min-w-0 flex-1 truncate text-xs font-medium text-foreground">{domain}</span>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Open in new tab"
        >
          <ExternalLink size={14} />
        </a>
        <button
          type="button"
          onClick={handleReload}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Reload"
        >
          <RefreshCw size={13} />
        </button>
        <button
          type="button"
          onClick={onClose}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Close"
        >
          <X size={14} />
        </button>
      </div>

      {/* Body */}
      <div className="relative flex-1">
        {isLoading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background">
            <Loader2 size={20} className="animate-spin text-muted-foreground" />
          </div>
        )}
        <iframe
          key={reloadKey}
          ref={iframeRef}
          src={url}
          title={domain}
          className="h-full w-full border-none"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          onLoad={handleLoad}
        />
      </div>
    </div>
  );
}

/** Right-side PDF preview panel.
 *  Fetches the file with auth (internal URLs) or plain fetch (external),
 *  creates a blob URL, and renders it with PdfViewer (PDFium WASM).
 */
function PdfPreviewPanel({ url, onClose, width }: { url: string; onClose: () => void; width: number }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);

  const filename = useMemo(() => {
    try {
      const parts = new URL(url).pathname.split('/');
      return decodeURIComponent(parts[parts.length - 1]) || 'Document.pdf';
    } catch {
      return 'Document.pdf';
    }
  }, [url]);

  const apiBase = useMemo(() => getApiBase(), []);
  const isInternal = useMemo(
    () => url.startsWith(apiBase) || url.startsWith('/api/') || url.startsWith('/'),
    [url, apiBase],
  );

  // Stable fetch URL — only recomputed when url or workspace changes.
  // Injects workspace_id for scopes that require it.
  const fetchUrl = useMemo(() => {
    if (!isInternal) return url;
    try {
      const u = new URL(url.startsWith('http') ? url : `${apiBase}${url}`);
      const scope = u.searchParams.get('scope') ?? '';
      const needsWorkspace = scope === 'platform_drive' || scope === 'system_drive' || scope === 'workspace';
      if (needsWorkspace && !u.searchParams.has('workspace_id') && currentWorkspaceId) {
        u.searchParams.set('workspace_id', currentWorkspaceId);
      }
      return u.toString();
    } catch {
      return url;
    }
  }, [url, isInternal, apiBase, currentWorkspaceId]);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    setBlobUrl(null);
    setIsLoading(true);
    setError(null);

    (async () => {
      try {
        const response = isInternal ? await authFetch(fetchUrl) : await fetch(fetchUrl);
        if (!response.ok) {
          let detail = `HTTP ${response.status}`;
          try {
            const body = await response.json();
            detail = body?.detail || detail;
          } catch { /* ignore */ }
          throw new Error(detail);
        }
        const blob = await response.blob();
        if (cancelled) return;
        const pdfBlob = blob.type.includes('pdf') ? blob : new Blob([blob], { type: 'application/pdf' });
        objectUrl = URL.createObjectURL(pdfBlob);
        setBlobUrl(objectUrl);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load PDF');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fetchUrl, isInternal]);

  return (
    <div className="flex min-h-0 flex-col border-border bg-background" style={{ width, minWidth: 280, maxWidth: 900 }}>
      {/* Header */}
      <div className="flex shrink-0 items-center gap-1.5 border-b border-border px-3 py-2">
        <span className="min-w-0 flex-1 truncate text-xs font-medium text-foreground">{filename}</span>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Open in new tab"
        >
          <ExternalLink size={14} />
        </a>
        <button
          type="button"
          onClick={onClose}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Close"
        >
          <X size={14} />
        </button>
      </div>

      {/* Body */}
      <div className="relative flex-1 min-h-0">
        {isLoading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background">
            <Loader2 size={20} className="animate-spin text-muted-foreground" />
          </div>
        )}
        {error && !isLoading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-sm text-destructive">
            <AlertCircle size={20} />
            <span className="text-center">{error}</span>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-workspace-accent hover:underline"
            >
              <ExternalLink size={14} /> Open in new tab
            </a>
          </div>
        )}
        {blobUrl && !error && (
          <PdfViewer src={blobUrl} />
        )}
      </div>
    </div>
  );
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

export function ChatInterface({ initialConversationId }: { initialConversationId?: string | null }) {
  const [mounted, setMounted] = useState(false);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [requestSentAt, setRequestSentAt] = useState<number | null>(null);
  const isSubmittingRef = useRef(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const streamControllerRef = useRef<AbortController | null>(null);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [showConnecting, setShowConnecting] = useState(false);
  const gotFirstTokenRef = useRef(false);
  const connectingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [attachedImages, setAttachedImages] = useState<string[]>([]); // Base64 images
  const [pendingFileAttachments, setPendingFileAttachments] = useState<string[]>([]); // Uploaded doc filenames
  const [imageError, setImageError] = useState<string | null>(null);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  // Web search — UI/API disabled until the feature is ready
  // const [searchEnabled, setSearchEnabled] = useState(false);
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
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [panelWidth, setPanelWidth] = useState(420);
  const [isPanelDragging, setIsPanelDragging] = useState(false);
  const isPanelDraggingRef = useRef(false);
  const panelDragStartXRef = useRef(0);
  const panelDragStartWidthRef = useRef(0);
  const [isDragOver, setIsDragOver] = useState(false);
  const dragCounterRef = useRef(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const autosizeComposer = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;

    // Match Tailwind `max-h-36` (9rem). Keep in sync with textarea class.
    const maxHeightPx = 144;
    el.style.height = 'auto';
    const nextHeight = Math.min(el.scrollHeight, maxHeightPx);
    el.style.height = `${nextHeight}px`;
    el.style.overflowY = el.scrollHeight > maxHeightPx ? 'auto' : 'hidden';
  }, []);

  useLayoutEffect(() => {
    autosizeComposer();
  }, [input, autosizeComposer]);

  const focusChatInput = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;

    // Ensure the textarea is in the tree and laid out (new conversation switches
    // can re-render the composer).
    requestAnimationFrame(() => {
      el.focus({ preventScroll: true });
      const end = el.value.length;
      try {
        el.setSelectionRange(end, end);
      } catch {
        // Some browsers can throw if the element isn't focusable yet; ignore.
      }
      autosizeComposer();
    });
  }, [autosizeComposer]);

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

  const router = useRouter();

  const {
    activeConversationId,
    selectedAgent,
    setSelectedAgent,
    createConversation,
    setActiveConversation,
    addMessage,
    updateLastMessage,
    getWorkspaceConversations,
    currentWorkspaceId,
    loadConversationMessages,
  } = useWorkspaceStore();

  const { socket, startTyping, stopTyping, onMessage } = useWebSocket();
  const { tab_title: tabTitle } = useTenant();

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

  // Sync URL slug → active conversation. When there's no slug (/chat base route),
  // reset to a blank new-chat state and pre-select the workspace default agent —
  // unless the user just explicitly picked an agent (sidebar/composer), which
  // must survive the navigation to the base chat route.
  useEffect(() => {
    if (initialConversationId) {
      setActiveConversation(initialConversationId);
      return;
    }
    setActiveConversation(null);
    if (useWorkspaceStore.getState().agentExplicitlySelected) return;
    const agents = useAgentsStore.getState().agents;
    const defaultAgent =
      agents.find((a) => a.isDefault && a.enabled) ??
      agents.find((a) => a.id === 'abi' && a.enabled) ??
      agents.find((a) => a.enabled);
    if (defaultAgent) setSelectedAgent(defaultAgent.id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialConversationId]);

  const pathname = usePathname();

  // Keep the URL in sync with the active conversation so each conversation has a shareable link.
  // Guarded against firing mid-workspace-switch: only rewrite the URL when the
  // pathname already points at the current workspace's chat route. Otherwise a
  // pending navigation to a different workspace (router.push from the sidebar)
  // would race with this effect and get reverted.
  useEffect(() => {
    if (!mounted) return;
    if (!currentWorkspaceId) return;
    const base = `/workspace/${currentWorkspaceId}/chat`;
    if (!pathname || !pathname.startsWith(`${base}`)) return;
    const target = activeConversationId ? `${base}/${activeConversationId}` : base;
    if (pathname === target) return;
    router.replace(target, { scroll: false });
  }, [activeConversationId, mounted, currentWorkspaceId, router, pathname]);

  // Narrow selector: only the active conversation's title — avoids re-renders on every streaming token.
  const activeConversationTitle = useWorkspaceStore((s) =>
    s.conversations.find((c) => c.id === s.activeConversationId)?.title
  );

  // Update the browser tab title with the active conversation name.
  // The 700 ms delay ensures we run after tenant-context.tsx's 600 ms re-apply,
  // which resets the title after every pathname change.
  useEffect(() => {
    if (!mounted) return;
    const t = setTimeout(() => {
      if (activeConversationTitle && activeConversationTitle !== 'New Conversation') {
        document.title = `${activeConversationTitle} | ${tabTitle}`;
      } else {
        document.title = `Chat | ${tabTitle}`;
      }
    }, 700);
    return () => clearTimeout(t);
  }, [activeConversationTitle, mounted, tabTitle]);

  // Keep the typing cursor in the chat bar whenever the active conversation changes
  // (including null = new chat state).
  useEffect(() => {
    if (!mounted) return;
    focusChatInput();
  }, [activeConversationId, mounted, focusChatInput]);

  // Consume one-shot composer seeds (e.g. "/skill-slug " from the sidebar).
  const pendingComposerText = useWorkspaceStore((s) => s.pendingComposerText);
  useEffect(() => {
    if (!mounted || !pendingComposerText) return;
    setInput(pendingComposerText);
    useWorkspaceStore.getState().setPendingComposerText(null);
    focusChatInput();
  }, [pendingComposerText, mounted, focusChatInput]);

  // ---------- Slash-command autocomplete ----------
  const [slashIndex, setSlashIndex] = useState(0);
  const [slashDismissed, setSlashDismissed] = useState(false);
  const workspaceSkills = useSkillsStore((s) =>
    currentWorkspaceId ? (s.skillsByWorkspace[currentWorkspaceId] ?? null) : null
  );

  // Active while the input is only "/partial-command" (no space typed yet).
  const slashQuery = useMemo(() => {
    const m = input.match(/^\/([a-zA-Z0-9_-]*)$/);
    return m ? m[1].toLowerCase() : null;
  }, [input]);

  const slashOptions = useMemo(() => {
    if (slashQuery === null) return [];
    const skills = workspaceSkills ?? [];
    const skillOptions = skills
      .filter((s) => s.enabled && s.slug.toLowerCase().includes(slashQuery))
      .sort((a, b) => {
        const ta = a.lastUsedAt ? new Date(a.lastUsedAt).getTime() : 0;
        const tb = b.lastUsedAt ? new Date(b.lastUsedAt).getTime() : 0;
        if (ta !== tb) return tb - ta;
        return a.slug.localeCompare(b.slug);
      })
      .map((s) => ({ slug: s.slug, name: s.name, description: s.description }));
    const builtinOptions = BUILTIN_SLASH_COMMANDS.filter((c) => c.slug.includes(slashQuery));
    return [...skillOptions, ...builtinOptions].slice(0, 8);
  }, [slashQuery, workspaceSkills]);

  useEffect(() => {
    setSlashIndex(0);
    setSlashDismissed(false);
  }, [slashQuery]);

  const showSlashMenu = slashOptions.length > 0 && !slashDismissed;

  const applySlashOption = useCallback(
    (slug: string) => {
      setInput(`/${slug} `);
      focusChatInput();
    },
    [focusChatInput]
  );

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
    // Skip fetch for locally-created drafts — they don't exist on the backend yet.
    if (conv?.isDraft) return;
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
          if (!existing) return prev;
          const next = new Map(prev);
          next.set(job_id, { ...existing, status: 'uploaded' });
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
    const abortRefs = ingestionAbortRefs.current;
    return () => {
      abortRefs.forEach((ctrl) => ctrl.abort());
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
          setIngestionJobs((prev) => {
            const next = new Map(prev);
            const existing = next.get(jobId);
            if (existing) next.set(jobId, { ...existing, status: 'uploaded' });
            return next;
          });
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
      // Synchronous ingestion result (small file, cache hit) — show uploaded state in bar
      const syncJobId = `sync-${file.name}-${Date.now()}`;
      setIngestionJobs((prev) => {
        const next = new Map(prev);
        next.set(syncJobId, { filename: file.name, status: 'uploaded', conversationId });
        return next;
      });
      setPendingFileAttachments((prev) => [...prev, file.name]);
      return;
    }

    setIngestionJobs((prev) => {
      const next = new Map(prev);
      next.set(result.job_id, { filename: file.name, status: 'queued', conversationId });
      return next;
    });

    await pollIngestionJob(result.job_id, file.name, conversationId, token);
    setPendingFileAttachments((prev) => [...prev, file.name]);
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
      // Synchronous ingestion (cache hit) — show uploaded state in bar
      const syncJobId = `sync-${filename}-${Date.now()}`;
      setIngestionJobs((prev) => {
        const next = new Map(prev);
        next.set(syncJobId, { filename, status: 'uploaded', conversationId });
        return next;
      });
      setPendingFileAttachments((prev) => [...prev, filename]);
      return;
    }

    setIngestionJobs((prev) => {
      const next = new Map(prev);
      next.set(result.job_id, { filename, status: 'queued', conversationId });
      return next;
    });

    await pollIngestionJob(result.job_id, filename, conversationId, token);
    setPendingFileAttachments((prev) => [...prev, filename]);
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

  const startVoiceRecording = useCallback(async () => {
    if (isLoading) {
      return;
    }
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
  }, [isLoading, stopVoiceStream]);

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

      const response = await fetch(`${getApiBase()}/api/transcribe`, {
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
      await handleSubmit(
        undefined,
        combined,
        selectedAgentAtSend,
        preservedConversationId ?? undefined
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Transcription failed';
      setVoiceError(message);
      setVoiceMode('idle');
      setRecordingSeconds(0);
      audioChunksRef.current = [];
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cancelVoiceRecording]);

  // Keyboard shortcuts:
  // - Ctrl/Cmd + K: start recording, or stop + send when already recording
  // - Ctrl/Cmd + L (or Escape): cancel current recording
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const hasCommandModifier = e.ctrlKey || e.metaKey;
      const key = e.key.toLowerCase();
      const hasNoExtraModifiers = !e.altKey && !e.shiftKey;

      if (hasCommandModifier && hasNoExtraModifiers && key === 'm') {
        e.preventDefault();
        e.stopPropagation();
        if (voiceMode === 'recording') {
          void confirmVoiceRecording();
        } else if (voiceMode === 'idle') {
          void startVoiceRecording();
        }
      } else if (
        (hasCommandModifier && hasNoExtraModifiers && key === 'm') ||
        e.key === 'Escape'
      ) {
        if (voiceMode !== 'recording') return;
        e.preventDefault();
        e.stopPropagation();
        cancelVoiceRecording();
      }
    };
    window.addEventListener('keydown', handler, true);
    return () => window.removeEventListener('keydown', handler, true);
  }, [voiceMode, confirmVoiceRecording, cancelVoiceRecording, startVoiceRecording]);

  // Cleanup mic resources if the component unmounts while recording
  useEffect(() => {
    return () => {
      stopVoiceStream();
    };
  }, [stopVoiceStream]);

  // Panel resize — global pointer handlers so the drag keeps working even when
  // the cursor leaves the handle strip.
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isPanelDraggingRef.current) return;
      const delta = panelDragStartXRef.current - e.clientX;
      setPanelWidth(Math.max(280, Math.min(900, panelDragStartWidthRef.current + delta)));
    };
    const onUp = () => {
      if (!isPanelDraggingRef.current) return;
      isPanelDraggingRef.current = false;
      setIsPanelDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      // Clean up in case component unmounts mid-drag
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, []);

  const handlePanelDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isPanelDraggingRef.current = true;
    setIsPanelDragging(true);
    panelDragStartXRef.current = e.clientX;
    panelDragStartWidthRef.current = panelWidth;
    // Lock cursor and disable text selection for the entire page during drag
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [panelWidth]);

  const handleSubmit = async (
    e?: React.FormEvent,
    messageOverride?: string,
    agentOverride?: string,
    conversationIdOverride?: string
  ) => {
    e?.preventDefault();
    if (isSubmittingRef.current) return;
    const sourceText = messageOverride !== undefined ? messageOverride : input;
    if ((!sourceText.trim() && attachedImages.length === 0 && pendingFileAttachments.length === 0) || isLoading) return;
    isSubmittingRef.current = true;
    const effectiveAgent = agentOverride ?? selectedAgent;

    const latestActiveConversationId = useWorkspaceStore.getState().activeConversationId;
    let conversationId = conversationIdOverride ?? latestActiveConversationId ?? activeConversationId;
    const existingConversationBeforeSend = conversationId
      ? useWorkspaceStore.getState().conversations.find((c) => c.id === conversationId)
      : null;

    // Create new conversation if none active
    if (!conversationId) {
      conversationId = createConversation();
    }

    // Keep the conversation's latest agent in sync locally — the backend does
    // the same in get_or_create_conversation on every send.
    if (existingConversationBeforeSend && existingConversationBeforeSend.agent !== effectiveAgent) {
      useWorkspaceStore.getState().setConversationAgent(conversationId, effectiveAgent);
    }

    // ---- Slash commands: /skills, /create-skill <desc>, /<skill_slug> [args] ----
    // The chat shows the compact "/command" the user typed; when a skill matches,
    // the expanded prompt is what gets sent to the model.
    let modelMessageOverride: string | null = null;
    const slashMatch = sourceText.trim().match(SLASH_COMMAND_RE);
    if (slashMatch) {
      const command = slashMatch[1].toLowerCase();
      const args = (slashMatch[2] || '').trim();
      const skillsStore = useSkillsStore.getState();
      const workspaceIdNow = useWorkspaceStore.getState().currentWorkspaceId;

      const finishLocalCommand = () => {
        if (messageOverride === undefined) {
          handleInputChange('');
        } else {
          setInput('');
        }
        isSubmittingRef.current = false;
      };

      if (command === 'skills') {
        addMessage(conversationId, { role: 'user', content: sourceText.trim() });
        addMessage(conversationId, {
          role: 'assistant',
          agent: effectiveAgent,
          content: formatSkillListing(skillsStore.getWorkspaceSkills(workspaceIdNow)),
        });
        finishLocalCommand();
        return;
      }
      if (command === 'create-skill') {
        modelMessageOverride = buildCreateSkillInstruction(args);
      } else {
        const skill = skillsStore.getSkillBySlug(workspaceIdNow, command);
        if (skill) {
          modelMessageOverride = args
            ? `${skill.prompt}\n\n---\n\nAdditional input from the user:\n${args}`
            : skill.prompt;
          void skillsStore.markSkillUsed(skill.id);
        } else {
          addMessage(conversationId, { role: 'user', content: sourceText.trim() });
          addMessage(conversationId, {
            role: 'system',
            content: `Unknown command \`/${command}\`. Type \`/skills\` to see available skills or \`/create-skill <description>\` to create one.`,
          });
          finishLocalCommand();
          return;
        }
      }
    }

    const currentImages = [...attachedImages]; // Copy before clearing
    const currentFileAttachments = [...pendingFileAttachments]; // Copy before clearing

    // Add user message with images and file attachments
    addMessage(conversationId, {
      role: 'user',
      content: sourceText.trim() || (attachedImages.length > 0 ? 'What is in this image?' : ''),
      images: currentImages.length > 0 ? currentImages : undefined,
      fileAttachments: currentFileAttachments.length > 0 ? currentFileAttachments : undefined,
    });

    const userMessage = sourceText.trim() || (currentImages.length > 0 ? 'What is in this image?' : '');
    // Only clear the input field if the message came from the input
    if (messageOverride === undefined) {
      handleInputChange('');
    } else {
      setInput('');
    }
    setAttachedImages([]); // Clear attached images after adding to message
    setPendingFileAttachments([]); // Clear file attachments after adding to message
    setImageError(null);
    // setSearchEnabled(false); // Reset search toggle after sending
    setRequestSentAt(Date.now());
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
      // Skip for drafts — they don't exist on the backend until the first send.
      if (
        existingConversationBeforeSend &&
        !existingConversationBeforeSend.isDraft &&
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

      // Skill invocations: the stored/displayed message is the compact
      // "/command", but the model receives the expanded skill prompt.
      if (modelMessageOverride && fullHistory.length > 0) {
        fullHistory[fullHistory.length - 1] = {
          ...fullHistory[fullHistory.length - 1],
          content: modelMessageOverride,
        };
      }

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
          content: '▌',
          // content: searchEnabled ? '🌐 Searching the web...' : '▌',
          agent: effectiveAgent,
          activityLine: 'Processing...',
          // activityLine: searchEnabled ? 'Web search in progress' : 'Processing...',
        });
        // Capture placeholder message id for controls. We keep it in a local
        // variable AND in React state — the SSE handler runs inside the same
        // async function so it can't rely on the freshly-set state (closures
        // capture stale values).
        let assistantMessageIdRef: string | null = null;
        {
          const convNow = useWorkspaceStore.getState().conversations.find(c => c.id === conversationId);
          const lastMsg = convNow?.messages[convNow.messages.length - 1];
          assistantMessageIdRef = lastMsg?.id || null;
          setStreamingMessageId(assistantMessageIdRef);
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
        let streamActivityLine: string | undefined = 'Processing...';
        let streamToolCalls: ToolCall[] = [];
        let hasDetailedActivity = false;
        let firstCallModelSeen = false;
        let lastEventWasToolResponse = false;

        const singleLine = (value: string) => value.replace(/\s+/g, ' ').trim();
        const truncateLine = (value: string, max = 140) =>
          value.length > max ? `${value.slice(0, max - 1)}…` : value;
        const formatToolName = (raw: string) =>
          raw
            .replace(/_/g, ' ')
            .replace(/\s+/g, ' ')
            .trim()
            .split(' ')
            .filter(Boolean)
            .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');

        const formatToolLabel = (raw: string): { prefix: 'Tool' | 'Routing to'; name: string } => {
          if (raw.startsWith('transfer_to')) {
            const target = raw.slice('transfer_to'.length).replace(/^_/, '');
            return { prefix: 'Routing to', name: formatToolName(target || raw) };
          }
          return { prefix: 'Tool', name: formatToolName(raw) };
        };

        const handleToolStartEvent = (rawTool: string, input?: string) => {
          const { prefix, name } = formatToolLabel(rawTool);
          const last = streamToolCalls[streamToolCalls.length - 1];
          if (last && last.status === 'running' && last.rawName === rawTool) {
            // Same tool still running — update input if provided
            if (input && !last.input) last.input = input;
            return;
          }
          // Mark previous running tool done
          if (last && last.status === 'running') last.status = 'done';
          streamToolCalls.push({
            id: `tc-${Date.now()}-${streamToolCalls.length}`,
            toolName: name,
            prefix,
            rawName: rawTool,
            status: 'running',
            ...(input ? { input } : {}),
          });
          streamActivityLine = prefix === 'Routing to' ? `${prefix} ${name}` : name;
          hasDetailedActivity = true;
        };

        const handleToolResponseEvent = (output: string) => {
          if (!output.trim()) return;

          // Prefer the most recent running tool call, otherwise attach to the
          // latest tool call entry. This supports streams where tool_response
          // arrives right after tool_usage but the status was already flipped.
          const reversed = [...streamToolCalls].reverse();
          const runningReverseIndex = reversed.findIndex(
            (call) => call.prefix === 'Tool' && call.status === 'running',
          );
          const recentToolReverseIndex = reversed.findIndex((call) => call.prefix === 'Tool');
          const selectedReverseIndex =
            runningReverseIndex !== -1 ? runningReverseIndex : recentToolReverseIndex;
          if (selectedReverseIndex === -1) return;

          const targetIndex = streamToolCalls.length - 1 - selectedReverseIndex;
          const target = streamToolCalls[targetIndex];
          target.status = 'done';
          target.output = output;
        };

        const handleAgentStepEvent = (
          stepType: 'agent_routing' | 'call_model',
          rawAgent: string,
          labelOverride?: string,
        ) => {
          const stepName = formatToolName(rawAgent);
          if (!stepName) return;

          const label = labelOverride ?? (stepType === 'call_model'
            ? 'Thinking'
            : `Routing to ${stepName}`);

          const last = streamToolCalls[streamToolCalls.length - 1];
          if (last && last.status === 'running') {
            last.status = 'done';
          }

          streamToolCalls.push({
            id: `tc-${Date.now()}-${streamToolCalls.length}`,
            toolName: label,
            prefix: 'Agent',
            rawName: `${stepType}:${rawAgent}`,
            status: 'running',
          });
          hasDetailedActivity = true;
        };

        const getStringValue = (...values: unknown[]): string => {
          for (const value of values) {
            if (typeof value === 'string') {
              const trimmed = value.trim();
              if (trimmed) return trimmed;
            }
          }
          return '';
        };

        const parseEvent = (payload: Record<string, unknown>) => {
          const event = getStringValue(payload.event);

          switch (event) {
            case 'tool':
            case 'tool_usage': {
              const rawTool = getStringValue(payload.tool, payload.data);
              if (!rawTool) return false;
              const input = getStringValue(payload.input, payload.data) || undefined;
              handleToolStartEvent(rawTool, input);
              streamActivityLine = formatToolName(rawTool);
              hasDetailedActivity = true;
              return true;
            }
            case 'tool_response': {
              const output = getStringValue(payload.output, payload.content, payload.data);
              handleToolResponseEvent(output);
              lastEventWasToolResponse = true;
              return true;
            }
            case 'agent.question': {
              const question = getStringValue(payload.question);
              if (!question) return false;
              streamActivityLine = `Question: ${truncateLine(singleLine(question), 110)}`;
              hasDetailedActivity = true;
              return true;
            }
            case 'call_model':
            case 'agent_calling': {
              const rawAgent = getStringValue(payload.agent, payload.data);
              if (!rawAgent) return false;
              if (!formatToolName(rawAgent)) return false;
              // Skip the very first call_model — fires before any tool use
              if (!firstCallModelSeen) {
                firstCallModelSeen = true;
                lastEventWasToolResponse = false;
                return true;
              }
              const callModelLabel = lastEventWasToolResponse
                ? 'Processing Tool Response'
                : 'Thinking';
              lastEventWasToolResponse = false;
              handleAgentStepEvent('call_model', rawAgent, callModelLabel);
              streamActivityLine = callModelLabel;
              hasDetailedActivity = true;
              return true;
            }
            case 'agent_routing': {
              const rawAgent = getStringValue(payload.agent, payload.data);
              if (!rawAgent) return false;
              const agentName = formatToolName(rawAgent);
              if (!agentName) return false;
              handleAgentStepEvent('agent_routing', rawAgent);
              streamActivityLine = `Routing to ${agentName}`;
              hasDetailedActivity = true;
              return true;
            }
            default:
              return false;
          }
        };

        const renderStreamingMessage = (withCaret: boolean) => {
          const body = thinkingContent
            ? `<think>${thinkingContent}</think>\n\n${responseContent}`
            : responseContent;

          const contentBody = body || '';
          const assembled = withCaret
            ? `${contentBody || '▌'}${contentBody ? '▌' : ''}`
            : `${contentBody}`;

          updateLastMessage(
            conversationId!,
            assembled.trimEnd() || '▌',
            undefined,
            undefined,
            streamActivityLine,
            streamToolCalls.length > 0 ? [...streamToolCalls] : undefined,
          );
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
            message: modelMessageOverride ?? userMessage,
            images: currentImages.length > 0 ? currentImages : null,
            messages: fullHistory,
            agent: effectiveAgent,
            provider: providerPayload,
            system_prompt: systemPrompt,
            search_enabled: false,
            // search_enabled: searchEnabled,
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
        let sseBuffer = '';

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            sseBuffer += decoder.decode(value || new Uint8Array(), { stream: !done });

            const lines = sseBuffer.split('\n');
            sseBuffer = done ? '' : lines.pop() ?? '';

            for (const rawLine of lines) {
              const line = rawLine.trimEnd();
              if (!line.startsWith('data: ')) continue;
              const data = line.slice(6).trim();
              if (!data || data === '[DONE]') continue;

              try {
                const parsed = JSON.parse(data);
                if (parsed.sources && Array.isArray(parsed.sources)) {
                  streamSources = parsed.sources as string[];
                }

                // First frame swap: the backend emits the real DB uuid for the
                // assistant row on the opening event. Replace the local
                // placeholder id so subsequent PATCHes (metadata, feedback)
                // hit the real row. We use the local ``assistantMessageIdRef``
                // because the React state ``streamingMessageId`` captured in
                // this closure is stale (the setState before the SSE loop
                // hasn't flushed yet).
                if (typeof parsed.assistant_message_id === 'string' && parsed.assistant_message_id) {
                  const backendId = parsed.assistant_message_id as string;
                  if (assistantMessageIdRef && assistantMessageIdRef !== backendId) {
                    useWorkspaceStore.getState().renameMessageId(
                      conversationId!,
                      assistantMessageIdRef,
                      backendId,
                    );
                    setStreamingMessageId(backendId);
                    assistantMessageIdRef = backendId;
                  }
                }

                if (parseEvent(parsed as Record<string, unknown>)) {
                  renderStreamingMessage(true);
                }
                if (parsed.content) {
                  // Once content starts streaming, any prior execution step has completed.
                  const runningStep = streamToolCalls[streamToolCalls.length - 1];
                  if (runningStep && runningStep.status === 'running') {
                    runningStep.status = 'done';
                  }
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
                // Re-throw non-JSON errors.
                // JSON parse failures are ignored for malformed lines and won't drop buffered partial lines.
                if (!(parseError instanceof SyntaxError)) {
                  throw parseError;
                }
              }
            }

            if (done) break;
          }
        }
        // Final: store full content with thinking duration
        const thinkingDuration = (Date.now() - thinkingStartTime) / 1000;
        const executionTime = requestSentAt ? (Date.now() - requestSentAt) / 1000 : undefined;
        const finalBody = thinkingContent
          ? `<think>${thinkingContent}</think>\n\n${responseContent}`
          : responseContent;
        const finalContent = finalBody.trim();
        // Mark any still-running tool as done
        streamToolCalls.forEach((t) => { if (t.status === 'running') t.status = 'done'; });
        const finalToolCalls = streamToolCalls.length > 0 ? [...streamToolCalls] : undefined;
        updateLastMessage(
          conversationId!,
          finalContent,
          thinkingDuration,
          streamSources.length > 0 ? streamSources : undefined,
          hasDetailedActivity ? streamActivityLine : null,
          finalToolCalls,
          executionTime,
        );
        // Persist execution metadata to backend
        if (streamingMessageId && (finalToolCalls || executionTime !== undefined)) {
          const apiUrl = getApiUrl();
          authFetch(
            `${apiUrl}/api/chat/conversations/${conversationId}/messages/${streamingMessageId}/metadata`,
            {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                execution_time: executionTime ?? null,
                steps: (finalToolCalls ?? []).map((t) => ({
                  tool_name: t.toolName,
                  prefix: t.prefix,
                  status: t.status,
                  input: t.input ?? null,
                  output: t.output ?? null,
                })),
                sources: streamSources,
              }),
            },
          ).catch(() => { /* non-blocking */ });
        }
      } catch (streamError) {
        // Gracefully handle user-initiated aborts
        if ((streamError as any)?.name === 'AbortError') {
          const finalBody = thinkingContent
            ? `<think>${thinkingContent}</think>\n\n${responseContent}`
            : responseContent;
          const finalContent = finalBody.trim();
          streamToolCalls.forEach((t) => { if (t.status === 'running') t.status = 'done'; });
          if (conversationId) {
            updateLastMessage(
              conversationId,
              finalContent,
              undefined,
              streamSources.length > 0 ? streamSources : undefined,
              hasDetailedActivity ? streamActivityLine : null,
              streamToolCalls.length > 0 ? [...streamToolCalls] : undefined,
            );
          }
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
            message: modelMessageOverride ?? userMessage,
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
              agent: effectiveAgent,
            });
          }
        }
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
      isSubmittingRef.current = false;
    }
  };

  const handleExportConversation = async () => {
    if (!activeConversation || activeConversation.messages.length === 0) {
      alert('No conversation to export');
      return;
    }

    try {
      const { authFetch } = await import('@/stores/auth');

      // Build inline metadata from local Zustand state so it's always present
      // regardless of whether the async PATCH has completed in the backend.
      const messagesMetadata = activeConversation.messages
        .filter((m) => m.role === 'assistant' && (m.toolCalls?.length || m.executionTime !== undefined))
        .map((m) => ({
          message_id: m.id,
          execution_time: m.executionTime ?? null,
          steps: (m.toolCalls ?? []).map((t) => ({
            tool_name: t.toolName,
            prefix: t.prefix,
            status: t.status,
            input: t.input ?? null,
            output: t.output ?? null,
          })),
          sources: m.sources ?? [],
        }));

      const response = await authFetch(
        `${getApiBase()}/api/chat/conversations/${activeConversation.id}/export`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ format: 'txt', messages_metadata: messagesMetadata }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to export conversation');
      }

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
    <div className="flex flex-1 min-h-0 relative">
    {/* Chat column */}
    <div className="flex flex-1 flex-col min-h-0 min-w-0">
      {/* Messages area */}
      <div className="flex-1 overflow-auto p-4 min-h-0">
        {!activeConversation || activeConversation.messages.length === 0 ? (
          <EmptyState
            selectedAgentName={selectedAgentData?.name || selectedAgent}
            logoUrl={selectedAgentData?.logoUrl ?? undefined}
            suggestions={selectedAgentData?.suggestions}
            onSuggestionClick={(prompt) => handleSubmit(undefined, prompt)}
            onSuggestionHover={(value) => setInput(value)}
            onSuggestionLeave={() => setInput('')}
          />
        ) : (
          <div className="mx-auto max-w-3xl space-y-6">
            {activeConversation.messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                currentSelectedAgent={selectedAgent}
                showConnecting={showConnecting}
                showStop={Boolean(streamingMessageId)}
                onStop={() => {
                  streamControllerRef.current?.abort();
                }}
                onPreviewUrl={setPreviewUrl}
                requestSentAt={requestSentAt}
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
          {/* Header with Export button (agent selector now lives in the chatbar) */}
          {activeConversation && activeConversation.messages.length > 0 && (
            <div className="mb-2 flex items-center justify-end gap-2">
              <button
                onClick={handleExportConversation}
                className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                title="Export conversation"
              >
                <Download size={16} />
              </button>
            </div>
          )}
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

            {/* Pending file attachment chips */}
            {pendingFileAttachments.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {pendingFileAttachments.map((filename, idx) => (
                  <div
                    key={idx}
                    className="group flex items-center gap-1.5 rounded-lg border border-border bg-muted px-2.5 py-1.5 text-xs text-foreground"
                  >
                    <FileText size={13} className="shrink-0 text-workspace-accent" />
                    <span className="max-w-[160px] truncate">{filename}</span>
                    <button
                      type="button"
                      onClick={() => setPendingFileAttachments((prev) => prev.filter((_, i) => i !== idx))}
                      className="ml-0.5 rounded p-0.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      title="Remove attachment"
                    >
                      <X size={11} />
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
                  const isUploaded = job.status === 'uploaded';
                  return (
                    <div
                      key={jobId}
                      className={cn(
                        'flex items-center gap-2 rounded-lg px-3 py-2 text-xs',
                        isFailed
                          ? 'bg-destructive/10 text-destructive'
                          : isUploaded
                            ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                            : 'bg-muted text-muted-foreground',
                      )}
                    >
                      {isFailed ? (
                        <AlertCircle size={14} className="shrink-0" />
                      ) : isUploaded ? (
                        <Check size={14} className="shrink-0" />
                      ) : (
                        <Loader2 size={14} className="shrink-0 animate-spin" />
                      )}
                      <span className="flex-1 truncate">
                        {isFailed
                          ? `Failed: ${job.filename}${job.error ? ` — ${job.error}` : ''}`
                          : isUploaded
                            ? `${job.filename} — uploaded`
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
                      {isUploaded && (
                        <button
                          type="button"
                          title="Dismiss"
                          className="ml-1 shrink-0 rounded-md p-0.5 hover:bg-green-500/20"
                          onClick={() => setIngestionJobs((prev) => { const next = new Map(prev); next.delete(jobId); return next; })}
                        >
                          <X size={11} />
                        </button>
                      )}
                    </div>
                  );
                })}
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
              <div className="relative px-4 pt-3 pb-1">
                {/* Slash-command autocomplete */}
                {showSlashMenu && (
                  <div className="absolute bottom-full left-2 right-2 z-50 mb-2 max-h-64 overflow-y-auto rounded-xl border border-border bg-popover p-1 shadow-lg">
                    {slashOptions.map((option, index) => (
                      <button
                        key={option.slug}
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          applySlashOption(option.slug);
                        }}
                        onMouseEnter={() => setSlashIndex(index)}
                        className={cn(
                          'flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors',
                          index === slashIndex ? 'bg-workspace-accent-10' : ''
                        )}
                      >
                        <span className="pt-0.5 font-mono text-xs text-workspace-accent">
                          /{option.slug}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-xs font-medium text-foreground">
                            {option.name}
                          </span>
                          {option.description && (
                            <span className="block truncate text-[11px] text-muted-foreground">
                              {option.description}
                            </span>
                          )}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => handleInputChange(e.target.value)}
                  onKeyDown={(e) => {
                    if (showSlashMenu) {
                      if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        setSlashIndex((i) => (i + 1) % slashOptions.length);
                        return;
                      }
                      if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        setSlashIndex((i) => (i - 1 + slashOptions.length) % slashOptions.length);
                        return;
                      }
                      if (e.key === 'Tab' || e.key === 'Enter') {
                        const selected = slashOptions[slashIndex] ?? slashOptions[0];
                        // Enter on a fully-typed command submits it; otherwise
                        // Enter/Tab completes the highlighted option.
                        if (!(e.key === 'Enter' && selected.slug === slashQuery)) {
                          e.preventDefault();
                          applySlashOption(selected.slug);
                          return;
                        }
                      }
                      if (e.key === 'Escape') {
                        e.preventDefault();
                        setSlashDismissed(true);
                        return;
                      }
                    }
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                  placeholder={
                    attachedImages.length > 0 ? 'Ask about the image...' : pendingFileAttachments.length > 0 ? 'Ask about the file...' : 'Send a message...'
                  }
                  // placeholder={searchEnabled ? "Search the web..." : attachedImages.length > 0 ? "Ask about the image..." : "Send a message..."}
                  className="max-h-36 min-h-[24px] w-full resize-none overflow-y-hidden bg-transparent text-sm outline-none ring-0 focus:ring-0 focus:outline-none placeholder:text-muted-foreground"
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
                      (attachedImages.length > 0 || pendingFileAttachments.length > 0) && 'bg-workspace-accent/15 text-workspace-accent'
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

                  {/* Search the web (globe) — disabled until feature is ready
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
                  */}
                </div>
                
                <div className="flex items-center gap-1">
                  {/* Agent selector dropdown */}
                  <AgentSelector compact />

                  {/* Model used by the selected agent */}
                  <ModelSelector />

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
                    title="Record voice message (Ctrl+M)"
                    aria-label="Record voice message (Ctrl+M)"
                  >
                    <Mic size={18} />
                  </button>

                  {/* Send button */}
                  <button
                    type="submit"
                    disabled={(!input.trim() && attachedImages.length === 0 && pendingFileAttachments.length === 0) || isLoading}
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-full transition-all',
                      (input.trim() || attachedImages.length > 0 || pendingFileAttachments.length > 0) && !isLoading
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
    {/* Full-viewport overlay during drag — keeps mouse events away from the iframe */}
    {isPanelDragging && (
      <div className="fixed inset-0 z-50 cursor-col-resize" />
    )}

    {/* Drag handle + preview panel */}
    {previewUrl && (
      <>
        {/* Resize handle — 8 px hit-area with a 1 px visible line in the centre */}
        <div
          className="group relative flex w-2 shrink-0 cursor-col-resize items-center justify-center"
          onMouseDown={handlePanelDragStart}
        >
          {/* Visible line */}
          <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border group-hover:bg-workspace-accent transition-colors" />
          {/* Grip dots centred on the line */}
          <div className="relative z-10 flex flex-col gap-[5px]">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="h-[3px] w-[3px] rounded-full bg-muted-foreground/40 group-hover:bg-workspace-accent transition-colors" />
            ))}
          </div>
        </div>
        {isPdfUrl(previewUrl) ? (
          <PdfPreviewPanel url={previewUrl} onClose={() => setPreviewUrl(null)} width={panelWidth} />
        ) : (
          <PreviewPanel url={previewUrl} onClose={() => setPreviewUrl(null)} width={panelWidth} />
        )}
      </>
    )}
    </div>
  );
}

// Maps CTA paths to their corresponding SidebarSection IDs.
const CTA_SECTION_MAP: Record<string, SidebarSection> = {
  '/marketplace': 'marketplace',
  '/apps': 'apps',
};

function EmptyState({
  selectedAgentName,
  logoUrl,
  suggestions,
  onSuggestionClick,
  onSuggestionHover,
  onSuggestionLeave,
}: {
  selectedAgentName: string;
  logoUrl?: string | null;
  suggestions?: Array<{ label: string; value: string; description?: string; disabled?: boolean; cta?: string }>;
  onSuggestionClick: (prompt: string) => void;
  onSuggestionHover?: (value: string) => void;
  onSuggestionLeave?: () => void;
}) {
  const router = useRouter();
  const { setActivePanelSection } = useWorkspaceStore();
  const { user } = useAuthStore();
  const resolvedLogoUrl = logoUrl ? getLogoUrl(logoUrl) : undefined;

  const firstName = user?.name?.split(' ')[0];
  const greeting = firstName ? `Hello, ${firstName}.` : 'Hello.';
  return (
    <div className="flex h-full flex-col items-center justify-center px-4">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-workspace-accent-10 overflow-hidden">
        {resolvedLogoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={resolvedLogoUrl}
            alt={selectedAgentName}
            className="h-full w-full object-contain p-1"
          />
        ) : (
          <Bot size={24} className="text-workspace-accent" />
        )}
      </div>
      <p className="mb-6 text-center text-muted-foreground">
        {greeting} Pick a suggestion or type a message to get started.
      </p>
      {Array.isArray(suggestions) && suggestions.length > 0 && (
        <div
          className="flex w-full max-w-lg flex-col gap-1.5"
          onMouseLeave={() => onSuggestionLeave?.()}
        >
          {suggestions.map((suggestion) => {
            const baseClass = cn(
              'glass-card flex min-w-0 items-center justify-between px-4 py-2.5 text-left transition-all',
              suggestion.disabled
                ? 'opacity-40 cursor-not-allowed'
                : 'hover:border-primary/30 hover:glow-primary-sm cursor-pointer'
            );

            const content = (
              <>
                <div className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium leading-tight">{suggestion.label}</span>
                  {suggestion.description && (
                    <span className="block truncate text-xs text-muted-foreground leading-snug">
                      {suggestion.description}
                    </span>
                  )}
                  {suggestion.disabled && (
                    <span className="block text-xs text-muted-foreground/60 italic">
                      Coming soon
                    </span>
                  )}
                </div>
                {!suggestion.disabled && (
                  <span className="ml-3 shrink-0 text-muted-foreground/40">›</span>
                )}
              </>
            );

            if (suggestion.cta && !suggestion.disabled) {
              const sectionId = (CTA_SECTION_MAP[suggestion.cta] ?? suggestion.cta.replace(/^\//, '')) as SidebarSection;
              return (
                <button
                  key={`${suggestion.label}:${suggestion.value}`}
                  onMouseEnter={() => onSuggestionHover?.(suggestion.label)}
                  onClick={() => {
                    setActivePanelSection(sectionId);
                    router.push(suggestion.cta!);
                  }}
                  className={baseClass}
                >
                  {content}
                </button>
              );
            }

            return (
              <button
                key={`${suggestion.label}:${suggestion.value}`}
                onMouseEnter={() => !suggestion.disabled && onSuggestionHover?.(suggestion.value)}
                onClick={() => !suggestion.disabled && onSuggestionClick(suggestion.value)}
                disabled={suggestion.disabled}
                className={baseClass}
              >
                {content}
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

function formatToolCallLabel(prefix: string, name: string): string {
  if (prefix === 'Agent') return name;
  if (prefix === 'Tool') return name;
  if (prefix === 'Routing to' || prefix === 'Handoff to') return `${prefix} ${name}`;
  return `${prefix}: ${name}`;
}

function ToolCallsDropdown({
  toolCalls,
  isProcessing,
  showStop,
  onStop,
  startTime,
}: {
  toolCalls: ToolCall[];
  isProcessing: boolean;
  showStop: boolean;
  onStop: () => void;
  startTime?: number | null;
}) {
  const [isOpen, setIsOpen] = useState(true);
  const [autoCollapsed, setAutoCollapsed] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [lastDurationSeconds, setLastDurationSeconds] = useState<number | null>(null);
  const wasProcessingRef = useRef(false);
  const processingStartRef = useRef<number | null>(null);

  const formatDuration = (seconds: number) => {
    if (seconds < 1) return '<1s';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  useEffect(() => {
    if (isProcessing) {
      wasProcessingRef.current = true;
      if (processingStartRef.current === null) {
        processingStartRef.current = startTime ?? Date.now();
        setElapsedSeconds(Math.floor((Date.now() - processingStartRef.current) / 1000));
      }
      if (autoCollapsed) {
        setIsOpen(true);
        setAutoCollapsed(false);
      }
    } else if (wasProcessingRef.current && !autoCollapsed) {
      const timer = setTimeout(() => {
        setIsOpen(false);
        setAutoCollapsed(true);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [isProcessing, autoCollapsed, startTime]);

  useEffect(() => {
    if (!isProcessing) {
      if (processingStartRef.current !== null) {
        const finalSeconds = Math.max(
          0,
          Math.floor((Date.now() - processingStartRef.current) / 1000),
        );
        setElapsedSeconds(finalSeconds);
        setLastDurationSeconds(finalSeconds);
        processingStartRef.current = null;
      }
      return;
    }

    const interval = setInterval(() => {
      if (processingStartRef.current === null) return;
      setElapsedSeconds(
        Math.max(0, Math.floor((Date.now() - processingStartRef.current) / 1000)),
      );
    }, 1000);

    return () => clearInterval(interval);
  }, [isProcessing]);

  const stepsLabel = `${toolCalls.length} step${toolCalls.length !== 1 ? 's' : ''}`;
  const headerLabel = isProcessing
    ? `Processing ${formatDuration(elapsedSeconds)}`
    : lastDurationSeconds !== null
      ? `Processed in ${formatDuration(lastDurationSeconds)} · ${stepsLabel}`
      : stepsLabel;

  return (
    <div className="mb-2 w-full">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
      >
        <Wrench size={11} className="shrink-0" />
        <span className="flex-1 truncate text-left">{headerLabel}</span>
        {isProcessing && (
          <span className="inline-flex shrink-0">
            <TypingDots />
          </span>
        )}
        {isProcessing && showStop && (
          <button
            type="button"
            className="ml-1 shrink-0 rounded px-1.5 py-0.5 text-xs hover:bg-muted"
            onClick={(e) => { e.stopPropagation(); e.preventDefault(); onStop(); }}
            title="Stop generation"
          >
            Stop
          </button>
        )}
        <ChevronDown size={11} className={cn('shrink-0 transition-transform', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <div className="mt-1.5 overflow-hidden rounded-lg border border-border/50 bg-background/50 divide-y divide-border/30">
          {toolCalls.map((tool) => (
            <ToolCallRow key={tool.id} tool={tool} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Pretty-print JSON (pprint-like indent); return original string if not JSON. */
function pprintLikeString(text: string): string {
  const trimmed = text.trim();
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) {
    return text;
  }
  try {
    return `${JSON.stringify(JSON.parse(trimmed), null, 4)}\n`;
  } catch {
    return text;
  }
}

/** Fixed-height viewport; `overflow-auto` scrolls vertically and horizontally when content overflows. */
const TOOL_DETAIL_PRE =
  'mt-0.5 max-h-48 w-full min-h-0 min-w-0 max-w-full overflow-auto whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-muted-foreground';

function formatToolUsageForClipboard(tool: ToolCall): string {
  const lines: string[] = [formatToolCallLabel(tool.prefix, tool.toolName)];
  if (tool.input?.trim()) {
    lines.push('', 'Input:', tool.input.trim());
  }
  if (tool.output?.trim()) {
    const out =
      tool.prefix === 'Tool' ? pprintLikeString(tool.output) : tool.output.trim();
    lines.push('', 'Output:', out.trimEnd());
  }
  return lines.join('\n');
}

function ToolCallRow({ tool }: { tool: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const [usageCopied, setUsageCopied] = useState(false);
  const isToolCall = tool.prefix === 'Tool';
  const hasToolResponse = Boolean(tool.output?.trim());
  const hasDetails = isToolCall ? hasToolResponse : Boolean(tool.input || tool.output);
  const prettyPrintedOutput = useMemo(
    () => (tool.output ? pprintLikeString(tool.output) : ''),
    [tool.output],
  );

  const clipboardText = useMemo(() => formatToolUsageForClipboard(tool), [tool]);

  const handleCopyToolUsage = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(clipboardText);
      setUsageCopied(true);
      window.setTimeout(() => setUsageCopied(false), 1600);
    } catch (e) {
      console.error('Failed to copy tool usage:', e);
    }
  }, [clipboardText]);

  return (
    <div className="min-w-0 px-3 py-2">
      <button
        type="button"
        disabled={!hasDetails}
        onClick={() => hasDetails && setExpanded((v) => !v)}
        className={cn(
          'flex w-full items-center gap-1.5 text-[11px]',
          hasDetails ? 'cursor-pointer hover:text-foreground' : 'cursor-default',
          'text-muted-foreground transition-colors',
        )}
      >
        {tool.status === 'running' ? (
          <Loader2 size={11} className="shrink-0 animate-spin text-workspace-accent" />
        ) : (
          <Check size={11} className="shrink-0 text-green-500 dark:text-green-400" />
        )}
        <span className="flex-1 text-left font-medium text-foreground/80">
          {formatToolCallLabel(tool.prefix, tool.toolName)}
        </span>
        {hasDetails && (
          <ChevronDown size={10} className={cn('shrink-0 transition-transform', expanded && 'rotate-180')} />
        )}
      </button>

      {expanded && hasDetails && (
        <div className="mt-2 min-w-0 space-y-2 pl-4">
          <div className="flex justify-end">
            <button
              type="button"
              aria-label={usageCopied ? 'Copied to clipboard' : 'Copy tool step to clipboard'}
              onClick={(e) => {
                e.stopPropagation();
                void handleCopyToolUsage();
              }}
              className="inline-flex items-center gap-1 rounded border border-border/70 px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              title="Copy this step (name, input, output)"
            >
              <Copy size={10} className="shrink-0" aria-hidden />
              {usageCopied ? 'Copied' : 'Copy'}
            </button>
          </div>
          {!isToolCall && tool.input && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/60">Input</p>
              <pre className={TOOL_DETAIL_PRE}>{tool.input}</pre>
            </div>
          )}
          {isToolCall && tool.output && (
            <pre className={TOOL_DETAIL_PRE}>{prettyPrintedOutput}</pre>
          )}
          {!isToolCall && tool.output && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/60">Output</p>
              <pre className={TOOL_DETAIL_PRE}>{tool.output}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Matches page titles that indicate a soft-404 ("Page Not Found", etc.)
const NOT_FOUND_TITLE_RE = /\b(404|not found|page not found|introuvable|doesn.t exist|no page)\b/i;

const MessageBubble = React.memo(function MessageBubble({
  message,
  currentSelectedAgent,
  showConnecting,
  showStop,
  onStop,
  onPreviewUrl,
  requestSentAt,
}: {
  message: Message;
  currentSelectedAgent: string;
  showConnecting: boolean;
  showStop: boolean;
  onStop: () => void;
  onPreviewUrl?: (url: string) => void;
  requestSentAt?: number | null;
}) {
  const isUser = message.role === 'user';
  const [showThinking, setShowThinking] = useState(false);
  const [autoCollapsed, setAutoCollapsed] = useState(false);
  const [copiedCodeKey, setCopiedCodeKey] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  // true = iframe-embeddable → open in preview panel
  // false = blocked / unreachable → open new tab
  // undefined = test in progress
  const [urlEmbeddability, setUrlEmbeddability] = useState<Record<string, boolean>>({});
  // true = URL responded (exists), false = network error (unreachable), undefined = testing
  const [urlExists, setUrlExists] = useState<Record<string, boolean>>({});
  const wasProcessingRef = useRef(false);
  const processingStartRef = useRef<number | null>(null);
  
  // Get user name and agent info for display
  const user = useAuthStore(state => state.user);
  const agents = useAgentsStore(state => state.agents);
  const agent = agents.find(a => a.id === message.agent);
  const isFromDifferentAgent = !isUser && Boolean(message.agent) && message.agent !== currentSelectedAgent;
  
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
  const responseForDisplay = (() => {
    if (isUser || typeof responseWithoutCaret !== 'string') return responseWithoutCaret;
    const matches = [...responseWithoutCaret.matchAll(/(?:^|\n)\s*(Tool|Agent):\s*[^\n]+/g)];
    if (matches.length === 0) return responseWithoutCaret;
    return matches[matches.length - 1][0].trim();
  })();

  // Still processing if:
  // - we have <think> content and either no visible response yet OR the response ends with the caret token, or
  // - no <think> section but the whole content is just the caret placeholder (initial placeholder)
  const isStillProcessing = !isUser && (
    (thinking !== null ? (!response || endsWithCaret) : (response === '▌'))
  );
  
  // Live elapsed timer while processing — starts from requestSentAt if provided
  useEffect(() => {
    if (isStillProcessing) {
      if (processingStartRef.current === null) {
        processingStartRef.current = requestSentAt ?? Date.now();
        setElapsedSeconds(Math.floor((Date.now() - processingStartRef.current) / 1000));
      }
      const interval = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - (processingStartRef.current ?? Date.now())) / 1000));
      }, 1000);
      return () => clearInterval(interval);
    } else {
      processingStartRef.current = null;
    }
  }, [isStillProcessing, requestSentAt]);

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

  // Show thinking section only when explicit reasoning content exists.
  const hasThinkingSection = !isUser && Boolean(thinking);
  const activityLine = !isUser
    ? (message.activityLine?.trim()
      || (isStillProcessing && showConnecting ? 'Processing...' : '')
      || (isStillProcessing ? 'Processing...' : ''))
    : '';

  const contentUrls = useMemo(() => {
    if (isUser || typeof responseForDisplay !== 'string' || isStillProcessing) return [];
    return extractUrlsFromContent(responseForDisplay);
  }, [isUser, responseForDisplay, isStillProcessing]);

  // Probe each URL with a hidden iframe to decide panel vs new-tab behaviour.
  // Known login-gated domains (e.g. LinkedIn) are marked blocked immediately.
  // ── Embeddability probe (hidden iframe) ──────────────────────────────────
  useEffect(() => {
    if (contentUrls.length === 0) return;
    let cancelled = false;
    const addedIframes: HTMLIFrameElement[] = [];
    const timers: ReturnType<typeof setTimeout>[] = [];

    contentUrls.forEach(url => {
      if (isLoginRequiredDomain(url) || isLikelyFileUrl(url) || url.startsWith(getApiBase())) {
        setUrlEmbeddability(prev => ({ ...prev, [url]: false }));
        return;
      }

      const iframe = document.createElement('iframe');
      iframe.style.cssText =
        'position:fixed;left:-9999px;width:0;height:0;opacity:0;pointer-events:none;border:none;';
      addedIframes.push(iframe);

      const resolve = (embeddable: boolean) => {
        if (cancelled) return;
        setUrlEmbeddability(prev => ({ ...prev, [url]: embeddable }));
        if (iframe.parentNode) iframe.parentNode.removeChild(iframe);
      };

      const t = setTimeout(() => resolve(false), 6000);
      timers.push(t);

      iframe.onload = () => {
        clearTimeout(t);
        try {
          const doc = iframe.contentDocument;
          resolve(!!(doc?.body && doc.body.innerHTML !== ''));
        } catch {
          resolve(true); // SecurityError = cross-origin loaded fine
        }
      };
      iframe.onerror = () => { clearTimeout(t); resolve(false); };

      iframe.src = url;
      document.body.appendChild(iframe);
    });

    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
      addedIframes.forEach(f => f.parentNode?.removeChild(f));
    };
  }, [contentUrls]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Existence probe (fetch) ───────────────────────────────────────────────
  // Strategy:
  //   1. CORS GET → real HTTP status + parse HTML <title> for "not found" text
  //   2. If CORS blocked → no-cors HEAD → basic reachability only
  //   3. If network error at either step → mark unreachable
  // Results are stored in urlValidityCache (module-level) so each URL is
  // probed at most twice (the two steps above) across all renders/instances.
  useEffect(() => {
    if (contentUrls.length === 0) return;
    let cancelled = false;
    const controllers: AbortController[] = [];

    contentUrls.forEach(async url => {
      // Serve from cache — skip network entirely for already-probed URLs.
      if (urlValidityCache.has(url)) {
        setUrlExists(prev => ({ ...prev, [url]: urlValidityCache.get(url)! }));
        return;
      }

      if (isLoginRequiredDomain(url)) {
        urlValidityCache.set(url, true);
        setUrlExists(prev => ({ ...prev, [url]: true }));
        return;
      }

      // Internal API URLs require auth — a plain fetch would always return 401.
      // Trust that they exist and skip the network probe.
      if (url.startsWith(getApiBase())) {
        urlValidityCache.set(url, true);
        setUrlExists(prev => ({ ...prev, [url]: true }));
        return;
      }

      const ctrl = new AbortController();
      controllers.push(ctrl);
      const timer = setTimeout(() => ctrl.abort(), 8000);

      try {
        // Step 1: HEAD request to get status + headers without downloading the body.
        // This avoids triggering a browser download for binary/attachment URLs.
        const headResp = await fetch(url, { method: 'HEAD', mode: 'cors', signal: ctrl.signal });
        clearTimeout(timer);
        if (cancelled) return;

        if (!headResp.ok) {
          urlValidityCache.set(url, false);
          setUrlExists(prev => ({ ...prev, [url]: false }));
          return;
        }

        const ct = headResp.headers.get('content-type') ?? '';
        const cd = headResp.headers.get('content-disposition') ?? '';

        // File attachment: exists but never embed in an iframe
        if (cd.toLowerCase().includes('attachment')) {
          urlValidityCache.set(url, true);
          setUrlExists(prev => ({ ...prev, [url]: true }));
          return;
        }

        // For HTML responses, do a GET to parse the <title> for soft-404 patterns
        if (ct.includes('text/html')) {
          const ctrl2 = new AbortController();
          controllers.push(ctrl2);
          const t2 = setTimeout(() => ctrl2.abort(), 8000);
          const getResp = await fetch(url, { method: 'GET', mode: 'cors', signal: ctrl2.signal });
          clearTimeout(t2);
          if (cancelled) return;
          const text = await getResp.text();
          if (cancelled) return;
          const doc = new DOMParser().parseFromString(text, 'text/html');
          const valid = !NOT_FOUND_TITLE_RE.test(doc.title);
          urlValidityCache.set(url, valid);
          setUrlExists(prev => ({ ...prev, [url]: valid }));
        } else {
          urlValidityCache.set(url, true);
          setUrlExists(prev => ({ ...prev, [url]: true }));
        }
      } catch {
        clearTimeout(timer);
        if (cancelled) return;

        // Step 2: CORS blocked → fall back to no-cors HEAD for basic reachability
        try {
          const ctrl2 = new AbortController();
          controllers.push(ctrl2);
          const t2 = setTimeout(() => ctrl2.abort(), 5000);
          await fetch(url, { method: 'HEAD', mode: 'no-cors', signal: ctrl2.signal });
          clearTimeout(t2);
          if (!cancelled) {
            urlValidityCache.set(url, true);
            setUrlExists(prev => ({ ...prev, [url]: true }));
          }
        } catch {
          if (!cancelled) {
            urlValidityCache.set(url, false);
            setUrlExists(prev => ({ ...prev, [url]: false }));
          }
        }
      }
    });

    return () => {
      cancelled = true;
      controllers.forEach(c => c.abort());
    };
  }, [contentUrls]); // eslint-disable-line react-hooks/exhaustive-deps

  // Strip trailing "Sources" blocks so they don't render inline — the
  // collapsible panel below handles display.
  const responseForRender = useMemo(() => {
    if (isUser || typeof responseForDisplay !== 'string') return responseForDisplay;
    return stripTrailingSources(responseForDisplay);
  }, [isUser, responseForDisplay]);

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
        if (isPdfUrl(href) && onPreviewUrl) {
          return (
            <a
              href={href}
              onClick={(e) => { e.preventDefault(); onPreviewUrl(href); }}
              className="text-workspace-accent hover:text-workspace-accent/90 underline underline-offset-2 break-all cursor-pointer"
            >
              {children ?? href}
            </a>
          );
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

        // ```skill blocks are agent-drafted skills — render the save card.
        if (language === 'skill') {
          return <SkillDraftCard raw={codeContent} />;
        }

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
    [copiedCodeKey, handleCopyCode, onPreviewUrl]
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

        {/* Attached files (for user messages) */}
        {isUser && message.fileAttachments && message.fileAttachments.length > 0 && (
          <div className={cn('flex flex-wrap gap-2 mb-2', 'justify-end')}>
            {message.fileAttachments.map((filename, idx) => (
              <div
                key={idx}
                className="flex items-center gap-1.5 rounded-lg border border-border bg-muted px-2.5 py-1.5 text-xs text-foreground"
              >
                <FileText size={13} className="shrink-0 text-workspace-accent" />
                <span className="max-w-[200px] truncate">{filename}</span>
              </div>
            ))}
          </div>
        )}
        
        {/* Processing / Processed indicator */}
        {hasThinkingSection && (
          <div className="w-full">
            <button
              onClick={() => thinking && setShowThinking(!showThinking)}
              className={cn(
                'flex items-center gap-1.5 text-xs text-muted-foreground transition-colors',
                thinking && !isStillProcessing && 'hover:text-foreground cursor-pointer'
              )}
              disabled={!thinking || isStillProcessing}
            >
              {isStillProcessing ? (
                <span className="font-medium tabular-nums">{formatDuration(elapsedSeconds)}</span>
              ) : (
                <span className="font-medium">
                  Reasoning
                </span>
              )}
              {thinking && !isStillProcessing && (
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
              '[&_p]:my-2 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-6 [&_li]:my-1 [&_li]:pt-0.5 [&_li]:leading-relaxed [&_h1]:text-base [&_h1]:font-bold [&_h1]:mt-4 [&_h1]:mb-1 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mt-3 [&_h2]:mb-1 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-2 [&_h3]:mb-1 [&_h4]:text-sm [&_h4]:font-semibold [&_h4]:mt-2 [&_h4]:mb-0.5 [&_h5]:text-sm [&_h5]:font-medium [&_h5]:mt-1.5 [&_h6]:text-sm [&_h6]:font-medium [&_h6]:mt-1 [&_code]:bg-background/50 [&_code]:px-1 [&_code]:rounded [&_code]:font-mono [&_pre]:my-0 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:border [&_pre]:border-border/70 [&_pre]:bg-background/80 [&_pre]:p-3 [&_pre]:text-xs [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:rounded-none [&_pre_code]:text-inherit'
          )}
        >
          {/* Sender name inside bubble (WhatsApp-style) */}
          <div className={cn(
            'text-xs font-bold mb-1.5 pb-1',
            isUser 
              ? 'text-left text-white border-b border-white/20' 
              : 'text-left text-workspace-accent border-b border-border'
          )}>
            <div className="flex items-center gap-2">
              <span>{senderName}</span>
              {/* {isFromDifferentAgent && (
                <span className="rounded-full border border-amber-300/50 bg-amber-100/70 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:border-amber-900/60 dark:bg-amber-900/30 dark:text-amber-300">
                  Not current agent
                </span>
              )} */}
            </div>
          </div>

          {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
            <ToolCallsDropdown
              toolCalls={message.toolCalls}
              isProcessing={isStillProcessing}
              showStop={showStop}
              onStop={onStop}
              startTime={requestSentAt}
            />
          )}
          {!isUser && !message.toolCalls && (activityLine || (isStillProcessing && showStop)) && (
            <div className="mb-2 flex min-w-0 items-center gap-2 text-[11px] text-muted-foreground">
              {activityLine ? (
                <span className="truncate">{activityLine}</span>
              ) : (
                <span className="truncate">Processing...</span>
              )}
              {isStillProcessing && (
                <span className="inline-flex shrink-0">
                  <TypingDots />
                </span>
              )}
              {isStillProcessing && showStop && (
                <button
                  className="ml-auto shrink-0 rounded px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-muted"
                  onClick={(e) => { e.preventDefault(); onStop(); }}
                  title="Stop generation"
                >
                  Stop
                </button>
              )}
            </div>
          )}
          
          {isUser ? (
            <p className="whitespace-pre-wrap text-left">
              {(response as string).match(URL_REGEX) ? linkifyText(response as string, true) : response}
            </p>
          ) : isStillProcessing ? (
            <div className="max-w-full">
              {responseForRender && (
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {responseForRender as string}
                </ReactMarkdown>
              )}
            </div>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {transformBareUrls(responseForRender as string)}
            </ReactMarkdown>
          )}
        </div>

        {/* RAG document source pills */}
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

        {/* URL sources extracted from message content */}
        {!isUser && contentUrls.length > 0 && (
          <div className="mt-3 rounded-xl border border-border/60 bg-background/50 px-3 py-2.5">
            <button
              type="button"
              onClick={() => setSourcesExpanded(v => !v)}
              className="flex w-full items-center gap-1.5 text-left"
            >
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
                className={`shrink-0 text-muted-foreground transition-transform duration-150 ${sourcesExpanded ? 'rotate-90' : ''}`}
              >
                <polyline points="9 18 15 12 9 6" />
              </svg>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {sourcesExpanded ? 'Sources' : `Sources (${contentUrls.length})`}
              </span>
            </button>
            {sourcesExpanded && (
              <div className="mt-2 space-y-1">
                {contentUrls.map((url, i) => {
                  const embeddable = urlEmbeddability[url]; // true | false | undefined (testing)
                  const exists = urlExists[url];             // true | false | undefined (testing)
                  const isTesting = exists === undefined;
                  const opensNewTab = embeddable === false;
                  const displayUrl = url.split('?')[0];
                  return (
                    <button
                      key={url}
                      type="button"
                      onClick={() => {
                        if (isPdfUrl(url)) {
                          onPreviewUrl?.(url);
                        } else if (opensNewTab) {
                          window.open(url, '_blank', 'noopener,noreferrer');
                        } else {
                          onPreviewUrl?.(url);
                        }
                      }}
                      className="group flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition-colors hover:bg-muted"
                    >
                      <span className="w-4 shrink-0 text-center tabular-nums text-muted-foreground">{i + 1}</span>
                      <span className="flex-1 truncate font-medium text-foreground">{displayUrl}</span>

                      {/* Existence validator */}
                      {isTesting ? (
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-label="Checking…" className="shrink-0 animate-spin text-muted-foreground opacity-40"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                      ) : exists ? (
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-label="URL reachable" className="shrink-0 text-emerald-500"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
                      ) : (
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-label="URL unreachable" className="shrink-0 text-red-500"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      )}

                      {/* Open action icon (visible on hover once tested) */}
                      {!isTesting && (
                        isPdfUrl(url) || !opensNewTab ? (
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
                        ) : (
                          <ExternalLink size={11} className="shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                        )
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Per-message actions */}
        {!isUser && !isStillProcessing && (
          <AssistantMessageActions message={message} />
        )}
        {isUser && <UserMessageActions message={message} />}
      </div>
    </div>
  );
});

function CopyMessageButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    const text = typeof content === 'string' ? content : '';
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try {
        document.execCommand('copy');
      } finally {
        document.body.removeChild(ta);
      }
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      onClick={handleCopy}
      title="Copy message"
      className="flex h-6 w-6 items-center justify-center rounded border border-transparent transition-colors hover:border-border hover:bg-muted/40"
    >
      {copied ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
    </button>
  );
}

function UserMessageActions({ message }: { message: Message }) {
  return (
    <div className="mt-1 flex items-center text-muted-foreground">
      <CopyMessageButton content={message.content} />
    </div>
  );
}

const FEEDBACK_TYPE_OPTIONS = [
  { value: 'inaccurate', label: 'Inaccurate response' },
  { value: 'off_topic', label: 'Off topic' },
  { value: 'hallucination', label: 'Hallucination / made-up information' },
  { value: 'incomplete', label: 'Incomplete response' },
  { value: 'unjustified_refusal', label: 'Unjustified refusal' },
  { value: 'tone', label: 'Inappropriate style or tone' },
  { value: 'harmful', label: 'Harmful or problematic content' },
  { value: 'other', label: 'Other' },
] as const;

function FeedbackDislikeDialog({
  open,
  initialDetails,
  submitting,
  onSubmit,
  onCancel,
}: {
  open: boolean;
  initialDetails: MessageFeedbackDetails | null;
  submitting: boolean;
  onSubmit: (details: MessageFeedbackDetails) => void;
  onCancel: () => void;
}) {
  const [type, setType] = useState<string>('');
  const [detail, setDetail] = useState<string>('');
  const [severity, setSeverity] = useState<number | null>(null);

  useEffect(() => {
    if (open) {
      setType(initialDetails?.type ?? '');
      setDetail(initialDetails?.detail ?? '');
      setSeverity(initialDetails?.severity ?? null);
    }
  }, [open, initialDetails]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onCancel();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, submitting, onCancel]);

  if (!open) return null;

  const handleSubmit = () => {
    onSubmit({
      type: type.trim() ? type : null,
      detail: detail.trim() ? detail.trim() : null,
      severity: severity ?? null,
    });
  };

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={() => !submitting && onCancel()}
      />
      <div className="relative z-10 mx-4 w-full max-w-md animate-in zoom-in-95 fade-in duration-200">
        <div className="border border-border bg-background p-6 shadow-2xl">
          <h3 className="text-base font-semibold text-foreground">Provide negative feedback</h3>

          <div className="mt-4 space-y-1">
            <label className="text-sm text-foreground">
              What type of issue would you like to report? (optional)
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full border border-border bg-muted/50 px-3 py-2 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-workspace-accent focus-visible:ring-offset-2 ring-offset-background"
            >
              <option value="">Select...</option>
              {FEEDBACK_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="mt-4 space-y-1">
            <label className="text-sm text-foreground">
              Please provide details: (optional)
            </label>
            <textarea
              value={detail}
              onChange={(e) => setDetail(e.target.value)}
              rows={4}
              className="w-full resize-none border border-border bg-muted/50 px-3 py-2 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-workspace-accent focus-visible:ring-offset-2 ring-offset-background"
              placeholder="Describe the issue you encountered..."
            />
          </div>

          <div className="mt-4 space-y-2">
            <label className="text-sm text-foreground">
              How unsatisfactory was this response? (optional)
            </label>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((value) => {
                const active = severity !== null && value <= severity;
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setSeverity(severity === value ? null : value)}
                    className={cn(
                      'flex h-8 w-8 items-center justify-center border text-sm transition-colors',
                      active
                        ? 'border-red-600/40 bg-red-50/40 text-red-600'
                        : 'border-border text-muted-foreground hover:bg-muted/40',
                    )}
                    aria-label={`Severity ${value}`}
                  >
                    {value}
                  </button>
                );
              })}
            </div>
            <p className="text-[11px] text-muted-foreground">
              1 = slightly unsatisfactory · 5 = completely unsatisfactory
            </p>
          </div>

          <p className="mt-4 text-xs text-muted-foreground">
            By submitting this report, you send the entire current conversation to our team to help
            us improve our models.
          </p>

          <div className="mt-6 flex justify-end gap-2">
            <button
              onClick={onCancel}
              disabled={submitting}
              className="px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="inline-flex items-center gap-2 bg-workspace-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-workspace-accent/90 disabled:opacity-60"
            >
              {submitting && <Loader2 size={12} className="animate-spin" />}
              Submit
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function AssistantMessageActions({ message }: { message: Message }) {
  const updateMessageFeedback = useWorkspaceStore((s) => s.updateMessageFeedback);
  const activeConversationId = useWorkspaceStore((s) => s.activeConversationId);
  const [busy, setBusy] = useState<null | 'like' | 'dislike'>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const feedback = message.feedback ?? null;
  const feedbackDetails = message.feedbackDetails ?? null;

  const sendFeedback = async (
    next: MessageFeedback | null,
    details: MessageFeedbackDetails | null,
  ) => {
    if (!activeConversationId) return false;
    const prev = feedback;
    const prevDetails = feedbackDetails;
    const which: 'like' | 'dislike' = next ?? (prev === 'like' ? 'like' : 'dislike');
    setBusy(which);
    updateMessageFeedback(activeConversationId, message.id, next, details);
    try {
      const { authFetch } = await import('@/stores/auth');
      const res = await authFetch(
        `${getApiBase()}/api/analytics/chats/${encodeURIComponent(activeConversationId)}/messages/${encodeURIComponent(message.id)}/feedback`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            feedback: next,
            feedback_type: details?.type ?? null,
            feedback_detail: details?.detail ?? null,
            feedback_severity: details?.severity ?? null,
          }),
        },
      );
      if (!res.ok) throw new Error(`Save failed (${res.status})`);
      return true;
    } catch (error) {
      console.error('Failed to save feedback:', error);
      updateMessageFeedback(activeConversationId, message.id, prev, prevDetails);
      return false;
    } finally {
      setBusy(null);
    }
  };

  const handleLikeClick = () => {
    if (feedback === 'like') {
      void sendFeedback(null, null);
    } else {
      void sendFeedback('like', null);
    }
  };

  const handleDislikeClick = () => {
    if (feedback === 'dislike') {
      void sendFeedback(null, null);
      return;
    }
    setDialogOpen(true);
  };

  const handleDialogSubmit = async (details: MessageFeedbackDetails) => {
    const ok = await sendFeedback('dislike', details);
    if (ok) setDialogOpen(false);
  };

  return (
    <>
      <div className="mt-1 flex items-center text-muted-foreground">
        <CopyMessageButton content={message.content} />
        <button
          onClick={handleLikeClick}
          disabled={busy !== null}
          title={feedback === 'like' ? 'Remove like' : 'Like'}
          className={`flex h-6 w-6 items-center justify-center rounded border border-transparent transition-colors hover:border-border hover:bg-muted/40 disabled:opacity-60 ${
            feedback === 'like' ? 'text-emerald-600 border-emerald-600/40 bg-emerald-50/40' : ''
          }`}
        >
          {busy === 'like' ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <ThumbsUp
              size={12}
              fill={feedback === 'like' ? 'currentColor' : 'none'}
              strokeWidth={feedback === 'like' ? 1.5 : 2}
            />
          )}
        </button>
        <button
          onClick={handleDislikeClick}
          disabled={busy !== null}
          title={feedback === 'dislike' ? 'Remove dislike' : 'Dislike'}
          className={`flex h-6 w-6 items-center justify-center rounded border border-transparent transition-colors hover:border-border hover:bg-muted/40 disabled:opacity-60 ${
            feedback === 'dislike' ? 'text-red-600 border-red-600/40 bg-red-50/40' : ''
          }`}
        >
          {busy === 'dislike' ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <ThumbsDown
              size={12}
              fill={feedback === 'dislike' ? 'currentColor' : 'none'}
              strokeWidth={feedback === 'dislike' ? 1.5 : 2}
            />
          )}
        </button>
      </div>
      <FeedbackDislikeDialog
        open={dialogOpen}
        initialDetails={feedbackDetails}
        submitting={busy === 'dislike'}
        onSubmit={handleDialogSubmit}
        onCancel={() => {
          if (busy !== 'dislike') setDialogOpen(false);
        }}
      />
    </>
  );
}

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
