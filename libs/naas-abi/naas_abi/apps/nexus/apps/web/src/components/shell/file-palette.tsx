'use client';

/**
 * FilePalette — VS Code-style Cmd+P file search.
 * Opens as a centred modal overlay; fuzzy-searches ~/aia via /api/lab/fs/search.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { FileCode, Folder, Clock, Search, X, CornerDownLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';

interface FileResult {
  name: string;
  path: string;
  type: 'file' | 'folder';
  modified?: string;
}

// File-extension → color (VS Code-ish)
function extColor(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  if (['ts', 'tsx'].includes(ext)) return 'text-blue-500';
  if (['js', 'jsx'].includes(ext)) return 'text-yellow-500';
  if (ext === 'py') return 'text-green-500';
  if (['md', 'mdx'].includes(ext)) return 'text-purple-400';
  if (['html', 'htm'].includes(ext)) return 'text-orange-500';
  if (['css', 'scss'].includes(ext)) return 'text-pink-500';
  if (['json', 'yaml', 'yml', 'toml'].includes(ext)) return 'text-amber-400';
  if (['sh', 'bash', 'zsh'].includes(ext)) return 'text-emerald-400';
  if (ext === 'sql') return 'text-cyan-400';
  return 'text-muted-foreground';
}

interface FilePaletteProps {
  open: boolean;
  onClose: () => void;
}

export function FilePalette({ open, onClose }: FilePaletteProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<FileResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const router = useRouter();

  const { openFiles, openFile, readHostFile } = useFilesStore();
  const { currentWorkspaceId } = useWorkspaceStore();

  const getWorkspacePath = (path: string) =>
    currentWorkspaceId ? `/workspace/${currentWorkspaceId}${path}` : path;

  // Recent files (already open in tabs) shown when query is empty
  const recentItems: FileResult[] = openFiles.map((p) => ({
    name: p.split('/').pop() ?? p,
    path: p,
    type: 'file' as const,
  }));

  // Search via API
  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await authFetch(
        `${getApiUrl()}/api/lab/fs/search?q=${encodeURIComponent(q)}&limit=40`
      );
      if (res.ok) {
        const data: FileResult[] = await res.json();
        setResults(data);
      }
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(query), 150);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, open, search]);

  // Reset on open
  useEffect(() => {
    if (open) {
      setQuery('');
      setResults([]);
      setActiveIndex(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  // Active items = recent (when empty) or search results
  const items = query.trim() ? results : recentItems;

  // Keep active item in view
  useEffect(() => {
    const el = listRef.current?.children[activeIndex] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  const openItem = useCallback(
    async (item: FileResult) => {
      if (item.type === 'folder') return; // folders not openable
      await readHostFile(item.path);
      openFile(item.path);
      router.push(getWorkspacePath('/lab'));
      onClose();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [openFile, readHostFile, router, currentWorkspaceId, onClose]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && items[activeIndex]) {
      e.preventDefault();
      openItem(items[activeIndex]);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center pt-[12vh]"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />

      {/* Palette */}
      <div className="relative z-10 w-full max-w-xl overflow-hidden rounded-xl border bg-card shadow-2xl">
        {/* Input row */}
        <div className="flex items-center gap-2 border-b px-4 py-3">
          <Search size={16} className="shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActiveIndex(0); }}
            onKeyDown={handleKeyDown}
            placeholder="Go to file…"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          {loading && (
            <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
          )}
          <button onClick={onClose} className="rounded p-0.5 text-muted-foreground hover:text-foreground">
            <X size={14} />
          </button>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-80 overflow-y-auto py-1">
          {items.length === 0 && !loading && (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">
              {query.trim() ? 'No files match.' : 'Start typing to search files…'}
            </p>
          )}

          {!query.trim() && recentItems.length > 0 && (
            <p className="px-4 py-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Recently opened
            </p>
          )}
          {query.trim() && results.length > 0 && (
            <p className="px-4 py-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              {results.length} result{results.length !== 1 ? 's' : ''}
            </p>
          )}

          {items.map((item, i) => {
            const dir = item.path.includes('/')
              ? item.path.split('/').slice(0, -1).join('/')
              : '';
            const isActive = i === activeIndex;
            return (
              <button
                key={item.path}
                onMouseEnter={() => setActiveIndex(i)}
                onClick={() => openItem(item)}
                className={cn(
                  'flex w-full items-center gap-3 px-4 py-2 text-left text-sm transition-colors',
                  isActive ? 'bg-primary/10 text-foreground' : 'text-foreground hover:bg-muted/50'
                )}
              >
                {item.type === 'folder' ? (
                  <Folder size={15} className="shrink-0 text-yellow-400" />
                ) : (
                  <FileCode size={15} className={cn('shrink-0', extColor(item.name))} />
                )}
                <span className="flex-1 truncate font-medium">
                  {query.trim()
                    ? highlightMatch(item.name, query)
                    : item.name}
                </span>
                {dir && (
                  <span className="ml-2 shrink-0 max-w-[180px] truncate text-[11px] text-muted-foreground">
                    {dir}
                  </span>
                )}
                {isActive && (
                  <span className="shrink-0 text-[10px] text-muted-foreground">
                    <CornerDownLeft size={11} />
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Footer hint */}
        <div className="flex items-center justify-between border-t px-4 py-2 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-2">
            <kbd className="rounded border bg-muted px-1 py-0.5">↑↓</kbd> navigate
            <kbd className="rounded border bg-muted px-1 py-0.5">↵</kbd> open
            <kbd className="rounded border bg-muted px-1 py-0.5">Esc</kbd> close
          </span>
          <span className="flex items-center gap-1">
            <Clock size={10} />
            <span>{recentItems.length} recent</span>
          </span>
        </div>
      </div>
    </div>
  );
}

/** Wraps matching characters in <strong> for bolding. */
function highlightMatch(text: string, query: string): React.ReactNode {
  const lower = text.toLowerCase();
  const q = query.toLowerCase();
  const idx = lower.indexOf(q);
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <strong className="text-primary">{text.slice(idx, idx + q.length)}</strong>
      {text.slice(idx + q.length)}
    </>
  );
}
