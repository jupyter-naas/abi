'use client';

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { usePathname, useRouter } from 'next/navigation';
import { Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { markAppsSkipRestore } from '@/app/workspace/[workspaceId]/apps/lib/apps-route';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { useFeature } from '@/hooks/use-feature';
import { getWorkspaceSwitchPath } from '@/lib/feature-access';
import {
  buildQuickOpenItems,
  conversationUpdatedAtMs,
  filterQuickOpenItems,
  groupQuickOpenItems,
  QUICK_OPEN_GROUP_LABEL,
  QUICK_OPEN_SECTIONS,
  type QuickOpenItem,
} from '@/lib/quick-open';
import { useAppsStore } from '@/stores/apps';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';

function modifierGlyph(): string {
  if (typeof navigator !== 'undefined' && /Mac|iPhone|iPad/i.test(navigator.platform)) {
    return '⌘';
  }
  return 'Ctrl+';
}

export function QuickOpen() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [mounted, setMounted] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [listBox, setListBox] = useState<{ top: number; left: number; width: number } | null>(null);

  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const conversations = useWorkspaceStore((s) => s.conversations);
  const setCurrentWorkspace = useWorkspaceStore((s) => s.setCurrentWorkspace);
  const setActiveConversation = useWorkspaceStore((s) => s.setActiveConversation);
  const setActivePanelSection = useWorkspaceStore((s) => s.setActivePanelSection);
  const syncWorkspaceConversations = useWorkspaceStore((s) => s.syncWorkspaceConversations);
  const workspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;

  const apps = useAppsStore((s) => s.apps);
  const fetchApps = useAppsStore((s) => s.fetchApps);
  const starredItems = useFilesStore((s) => s.starredItems);
  const setStarredNavigation = useFilesStore((s) => s.setStarredNavigation);
  const setActiveSource = useFilesStore((s) => s.setActiveSource);

  const canMaps = useFeature('maps');
  const canChat = useFeature('chat');
  const canFiles = useFeature('files');
  const canDatasets = useFeature('datasets');
  const canAgents = useFeature('agents');
  const canApps = useFeature('apps');
  const canMarketplace = useFeature('marketplace');
  const canSearch = useFeature('search');
  const canOntology = useFeature('ontology');
  const canGraph = useFeature('graph');
  const canCode = useFeature('code');
  const canSlides = useFeature('slides');
  const canSettingsWorkspace = useFeature('settings.workspace');

  const featureOn: Record<string, boolean> = {
    apps: canApps,
    agents: canAgents,
    files: canFiles,
    chat: canChat,
    search: canSearch,
    maps: canMaps,
    ontology: canOntology,
    graph: canGraph,
    datasets: canDatasets,
    slides: canSlides,
    code: canCode,
    marketplace: canMarketplace,
    'settings.workspace': canSettingsWorkspace,
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    setQuery('');
    setActiveIndex(0);
  }, []);

  const openPalette = useCallback(() => {
    setOpen(true);
    setQuery('');
    setActiveIndex(0);
  }, []);

  useLayoutEffect(() => {
    if (!open || !wrapRef.current) {
      setListBox(null);
      return;
    }
    const rect = wrapRef.current.getBoundingClientRect();
    setListBox({ top: rect.bottom + 4, left: rect.left, width: rect.width });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [open]);

  useEffect(() => {
    if (!open || !currentWorkspaceId) return;
    void fetchApps(currentWorkspaceId);
    void syncWorkspaceConversations(currentWorkspaceId);
  }, [open, currentWorkspaceId, fetchApps, syncWorkspaceConversations]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 'p') return;
      if (e.shiftKey) return;
      e.preventDefault();
      e.stopPropagation();
      if (open) close();
      else openPalette();
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [open, openPalette, close]);

  const catalog = useMemo(() => {
    if (!currentWorkspaceId) return [];
    const sections = QUICK_OPEN_SECTIONS.filter((section) => {
      if (!section.feature) return true;
      return featureOn[section.feature];
    }).map((section) => ({
      id: section.id,
      label: section.label,
      href: getWorkspacePath(currentWorkspaceId, section.href),
    }));
    const chats = conversations
      .filter((c) => c.workspaceId === currentWorkspaceId && !c.archived)
      .sort((a, b) => conversationUpdatedAtMs(b.updatedAt) - conversationUpdatedAtMs(a.updatedAt))
      .slice(0, 20)
      .map((c) => ({ id: c.id, title: c.title }));
    const listedApps = apps
      .filter((a) => a.enabled && a.installed && a.url)
      .map((a) => ({ id: a.app_id, name: a.name }));
    const files = starredItems
      .filter((item) => item.workspaceId === currentWorkspaceId)
      .map((item) => ({
        source: item.source,
        path: item.path,
        name: item.name,
        type: item.type,
      }));
    return buildQuickOpenItems({
      workspaceId: currentWorkspaceId,
      workspaces: workspaces.map((w) => ({ id: w.id, name: w.name })),
      sections,
      apps: listedApps,
      chats,
      files,
    });
    // Individual feature flags are listed below; featureOn is derived from them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    currentWorkspaceId,
    workspaces,
    conversations,
    apps,
    starredItems,
    canMaps,
    canChat,
    canFiles,
    canDatasets,
    canAgents,
    canApps,
    canMarketplace,
    canSearch,
    canOntology,
    canGraph,
    canCode,
    canSlides,
    canSettingsWorkspace,
  ]);

  const results = useMemo(() => filterQuickOpenItems(catalog, query), [catalog, query]);
  const groups = useMemo(() => groupQuickOpenItems(results), [results]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const node = listRef.current?.querySelector<HTMLElement>(`[data-quick-open-index="${activeIndex}"]`);
    node?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex, open]);

  const run = useCallback(
    (item: QuickOpenItem) => {
      if (!currentWorkspaceId) return;
      const action = item.action;
      if (action.kind === 'workspace') {
        if (action.workspaceId !== currentWorkspaceId) {
          const target = workspaces.find((w) => w.id === action.workspaceId);
          setActiveConversation(null);
          markAppsSkipRestore();
          setCurrentWorkspace(action.workspaceId);
          router.push(
            getWorkspaceSwitchPath({
              pathname,
              targetWorkspaceId: action.workspaceId,
              role: target?.currentUserRole,
              workspaceFlags: target?.featureFlags,
            }),
          );
        }
        close();
        return;
      }
      if (action.kind === 'file') {
        if (action.type === 'folder') {
          setStarredNavigation({ source: action.source, path: action.path });
        } else {
          const parentPath = action.path.includes('/')
            ? action.path.substring(0, action.path.lastIndexOf('/'))
            : '';
          setStarredNavigation({
            source: action.source,
            path: parentPath,
            previewPath: action.path,
          });
        }
        setActiveSource(action.source);
        setActivePanelSection('files');
        router.push(getWorkspacePath(currentWorkspaceId, '/files'));
        close();
        return;
      }
      if (action.panel === null) setActivePanelSection(null);
      else if (action.panel) setActivePanelSection(action.panel as SidebarSection);
      router.push(action.href);
      close();
    },
    [
      currentWorkspaceId,
      workspaces,
      pathname,
      router,
      setActiveConversation,
      setCurrentWorkspace,
      setActivePanelSection,
      setStarredNavigation,
      setActiveSource,
      close,
    ],
  );

  const onInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, Math.max(results.length - 1, 0)));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const item = results[activeIndex];
      if (item) run(item);
    }
  };

  const workspaceName = workspace?.name || 'Search';
  const shortcut = mounted ? `${modifierGlyph()}P` : '⌘P';

  return (
    <div ref={wrapRef} className="relative w-[min(32rem,calc(100vw-22rem))] max-w-[32rem]">
      <button
        type="button"
        onClick={() => (open ? inputRef.current?.focus() : openPalette())}
        className={cn(
          'flex h-8 w-full items-center gap-2 rounded-md border px-2.5 text-left text-sm transition-colors',
          open
            ? 'border-workspace-accent/40 bg-background text-foreground shadow-sm'
            : 'border-border/60 bg-muted/40 text-muted-foreground hover:border-border hover:bg-muted/70 hover:text-foreground',
        )}
        aria-label={`Search ${workspaceName}`}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls="quick-open-list"
      >
        <Search size={14} className="shrink-0 opacity-70" />
        {open ? (
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKeyDown}
            onClick={(e) => e.stopPropagation()}
            placeholder={workspaceName}
            className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            aria-autocomplete="list"
          />
        ) : (
          <>
            <span className="min-w-0 flex-1 truncate">{workspaceName}</span>
            <kbd className="hidden shrink-0 rounded border border-border/70 bg-background/80 px-1.5 py-0.5 font-sans text-[10px] text-muted-foreground sm:inline">
              {shortcut}
            </kbd>
          </>
        )}
      </button>

      {open && mounted
        ? createPortal(
            <>
              <div className="fixed inset-0 z-[250]" onMouseDown={close} />
              <div
                id="quick-open-list"
                ref={listRef}
                role="listbox"
                className="fixed z-[260] max-h-[min(28rem,70vh)] overflow-y-auto border border-border bg-background shadow-xl"
                style={{
                  top: listBox?.top ?? 56,
                  left: listBox?.left ?? 0,
                  width: listBox?.width ?? 480,
                }}
              >
                {groups.length === 0 ? (
                  <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                    {query.trim() ? 'No matches' : 'Nothing to jump to yet'}
                  </p>
                ) : (
                  groups.map((entry) => (
                    <div key={entry.group}>
                      <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                        {QUICK_OPEN_GROUP_LABEL[entry.group]}
                      </div>
                      {entry.items.map((item) => {
                        const index = results.indexOf(item);
                        const active = index === activeIndex;
                        return (
                          <button
                            key={item.id}
                            type="button"
                            role="option"
                            aria-selected={active}
                            data-quick-open-index={index}
                            onMouseEnter={() => setActiveIndex(index)}
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => run(item)}
                            className={cn(
                              'flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm',
                              active ? 'bg-muted text-foreground' : 'text-foreground/90 hover:bg-muted/70',
                            )}
                          >
                            <span className="min-w-0 flex-1 truncate">{item.label}</span>
                            {item.hint ? (
                              <span className="shrink-0 text-[11px] text-muted-foreground">{item.hint}</span>
                            ) : null}
                          </button>
                        );
                      })}
                    </div>
                  ))
                )}
              </div>
            </>,
            document.body,
          )
        : null}
    </div>
  );
}
