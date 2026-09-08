'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronDown, FileText, Presentation, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { SLIDES_DECK_UPDATED_EVENT, type SlidesRuntimeStatus } from '@/stores/slides';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { type SlidesProjectTree } from '@/components/shell/sidebar/slides-tree';
import { activeSuggestions, suggestionHint, type ChatSuggestion } from '@/lib/suggestion-row';
import {
  slidesComposerFiles,
  slidesComposerRuntimeSuffix,
} from './slides-composer-model';

export {
  flattenSlidesComposerFiles,
  slidesComposerFallbackFiles,
  slidesComposerFiles,
  slidesComposerRuntimeSuffix,
} from './slides-composer-model';

type ComposerTab = 'suggestions' | 'files';

const CTA_SECTION_MAP: Record<string, SidebarSection> = {
  '/marketplace': 'marketplace',
  '/apps': 'apps',
};

export function SlidesComposerTabs({
  slug,
  path,
  workspaceId,
  suggestions,
  onSuggestionClick,
  onSuggestionHover,
  onSuggestionLeave,
}: {
  slug: string;
  path: string;
  workspaceId: string | null | undefined;
  suggestions?: ChatSuggestion[];
  onSuggestionClick: (prompt: string) => void;
  onSuggestionHover?: (value: string) => void;
  onSuggestionLeave?: () => void;
}) {
  const router = useRouter();
  const setActivePanelSection = useWorkspaceStore((s) => s.setActivePanelSection);
  const [tab, setTab] = useState<ComposerTab>('suggestions');
  const [open, setOpen] = useState(true);
  const [tree, setTree] = useState<SlidesProjectTree | null>(null);
  const chips = useMemo(() => activeSuggestions(suggestions), [suggestions]);
  const files = useMemo(() => slidesComposerFiles(tree, path), [tree, path]);

  const fetchTree = useCallback(async () => {
    if (!workspaceId || !slug) return;
    try {
      const res = await authFetch(
        `/api/slides/projects/${encodeURIComponent(slug)}/tree` +
          `?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (!res.ok) return;
      setTree((await res.json()) as SlidesProjectTree);
    } catch {
      // Keep the open-deck fallback. Do not invent a file list.
    }
  }, [workspaceId, slug]);

  useEffect(() => {
    setTree(null);
    void fetchTree();
  }, [fetchTree, slug]);

  useEffect(() => {
    const onUpdated = (event: Event) => {
      const updated = (event as CustomEvent<{ slug?: string }>).detail?.slug;
      if (updated && updated !== slug) return;
      void fetchTree();
    };
    window.addEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
  }, [fetchTree, slug]);

  const selectTab = (next: ComposerTab) => {
    setTab(next);
    setOpen(true);
  };

  const activateSuggestion = (suggestion: ChatSuggestion) => {
    if (suggestion.cta) {
      const sectionId = (CTA_SECTION_MAP[suggestion.cta] ??
        suggestion.cta.replace(/^\//, '')) as SidebarSection;
      setActivePanelSection(sectionId);
      router.push(suggestion.cta);
      return;
    }
    onSuggestionClick(suggestion.value);
  };

  return (
    <div className="chat-slides-composer-chrome" data-slides-composer-chrome="">
      <div className={cn('chat-slides-composer-drawer', open && 'is-open')}>
        <div className="chat-slides-composer-drawer-header">
          <button
            type="button"
            className="chat-slides-composer-drawer-toggle"
            aria-expanded={open}
            aria-label={open ? 'Collapse composer extras' : 'Expand composer extras'}
            onClick={() => setOpen((value) => !value)}
          >
            <ChevronDown
              size={14}
              className={cn(!open && 'chat-slides-composer-drawer-toggle-closed')}
            />
          </button>
          <div className="chat-slides-composer-tabs" role="tablist" aria-label="Composer extras">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'suggestions'}
              className={cn('chat-slides-composer-tab', tab === 'suggestions' && 'is-active')}
              onClick={() => selectTab('suggestions')}
            >
              Suggestions ({chips.length})
            </button>
            <span className="chat-slides-composer-tab-sep" aria-hidden>
              |
            </span>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'files'}
              className={cn('chat-slides-composer-tab', tab === 'files' && 'is-active')}
              onClick={() => selectTab('files')}
            >
              Files ({files.length})
            </button>
          </div>
        </div>
        {open ? (
          <div className="chat-slides-composer-drawer-body">
            {tab === 'suggestions' ? (
              chips.length > 0 ? (
                <ul
                  className="chat-slides-composer-list"
                  aria-label="Suggested questions"
                  onMouseLeave={() => onSuggestionLeave?.()}
                >
                  {chips.map((suggestion) => {
                    const hint = suggestionHint(suggestion);
                    return (
                      <li key={`${suggestion.label}:${suggestion.value}`}>
                        <button
                          type="button"
                          className="chat-slides-composer-row"
                          onMouseEnter={() =>
                            onSuggestionHover?.(
                              suggestion.cta ? suggestion.label : suggestion.value,
                            )
                          }
                          onClick={() => activateSuggestion(suggestion)}
                        >
                          <Sparkles size={13} className="chat-slides-composer-row-icon text-workspace-accent" />
                          <span className="chat-slides-composer-row-text">
                            <span className="chat-slides-composer-row-name">{suggestion.label}</span>
                            {hint ? (
                              <span className="chat-slides-composer-row-hint">{hint}</span>
                            ) : null}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="chat-slides-composer-empty">No suggestions for this agent</p>
              )
            ) : files.length > 0 ? (
              <ul className="chat-slides-composer-list" aria-label="Deck files">
                {files.map((file) => (
                  <li
                    key={file.path}
                    className={cn('chat-slides-composer-row is-static', file.open && 'is-open')}
                    title={file.path}
                  >
                    <FileText size={13} className="chat-slides-composer-row-icon text-workspace-accent" />
                    <span className="chat-slides-composer-row-text">
                      <span className="chat-slides-composer-row-name">{file.name}</span>
                      <span className="chat-slides-composer-row-hint">{file.path}</span>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="chat-slides-composer-empty">No files listed for this deck</p>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function SlidesComposerContext({
  title,
  path,
  runtime,
}: {
  title: string;
  path: string;
  runtime?: SlidesRuntimeStatus | null;
}) {
  const suffix = slidesComposerRuntimeSuffix(runtime);
  return (
    <div
      className="chat-slides-composer-context"
      data-slides-composer-context=""
      title={[`Editing ${title}`, path, suffix].filter(Boolean).join(' · ')}
    >
      <Presentation size={13} className="shrink-0 text-workspace-accent" />
      <span className="min-w-0 truncate">
        Editing{' '}
        <span className="font-medium text-foreground">{title}</span>
        {' · '}
        {path}
        {suffix ? ` · ${suffix}` : ''}
      </span>
    </div>
  );
}
