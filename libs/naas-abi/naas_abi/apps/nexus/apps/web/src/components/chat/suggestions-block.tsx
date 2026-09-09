'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { activeSuggestions, suggestionHint, type ChatSuggestion } from '@/lib/suggestion-row';

// Maps CTA paths to their corresponding SidebarSection IDs.
const CTA_SECTION_MAP: Record<string, SidebarSection> = {
  '/marketplace': 'marketplace',
  '/apps': 'apps',
};

// Open/collapsed state per agent, persisted to localStorage so it survives
// agent switches, conversation changes, and page reloads. An in-memory
// cache avoids re-parsing the stored blob on every render.
const STORAGE_KEY = 'nexus.chat.suggestionsOpenByAgent';
const openStateCache = new Map<string, boolean>();

function readStoredOpenMap(): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

function loadOpenState(agentId: string): boolean {
  const cached = openStateCache.get(agentId);
  if (cached !== undefined) return cached;
  const value = readStoredOpenMap()[agentId] ?? false;
  openStateCache.set(agentId, value);
  return value;
}

function saveOpenState(agentId: string, value: boolean): void {
  openStateCache.set(agentId, value);
  if (typeof window === 'undefined') return;
  try {
    const map = readStoredOpenMap();
    map[agentId] = value;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // Best-effort persistence only.
  }
}

/**
 * Agent-scoped "Suggestions" container above the composer: a single
 * clickable header that expands in place to reveal the full suggestion
 * list. Sits flush on top of the composer input box (shared border, no
 * gap) via `.chat-suggestions-block` in chat-agent-selector.css.
 */
export function SuggestionsBlock({
  agentId,
  suggestions,
  onSuggestionClick,
  onSuggestionHover,
  onSuggestionLeave,
}: {
  agentId?: string | null;
  suggestions?: ChatSuggestion[];
  onSuggestionClick: (prompt: string) => void;
  onSuggestionHover?: (value: string) => void;
  onSuggestionLeave?: () => void;
}) {
  const router = useRouter();
  const setActivePanelSection = useWorkspaceStore((s) => s.setActivePanelSection);
  const [open, setOpen] = useState(() => (agentId ? loadOpenState(agentId) : false));
  const chips = useMemo(() => activeSuggestions(suggestions), [suggestions]);

  // Restore the remembered state whenever the agent underneath it changes.
  useEffect(() => {
    setOpen(agentId ? loadOpenState(agentId) : false);
  }, [agentId]);

  const toggleOpen = () => {
    setOpen((value) => {
      const next = !value;
      if (agentId) saveOpenState(agentId, next);
      return next;
    });
  };

  if (chips.length === 0) return null;

  const activate = (suggestion: ChatSuggestion) => {
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
    <div className="chat-suggestions-block rounded-t-2xl border border-border/50">
      <button
        type="button"
        className="chat-suggestions-toggle"
        aria-expanded={open}
        onClick={toggleOpen}
      >
        <ChevronRight
          size={12}
          className={cn('chat-suggestions-toggle-chevron shrink-0', open && 'is-open')}
        />
        <span className="chat-suggestions-toggle-label">{chips.length} Suggestions</span>
      </button>
      {open && (
        <ul
          className="chat-slides-composer-list chat-suggestions-list"
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
                    onSuggestionHover?.(suggestion.cta ? suggestion.label : suggestion.value)
                  }
                  onClick={() => activate(suggestion)}
                >
                  <span className="chat-slides-composer-row-text">
                    <span className="chat-slides-composer-row-name">{suggestion.label}</span>
                    {hint ? <span className="chat-slides-composer-row-hint">{hint}</span> : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
