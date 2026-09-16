'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { activeSuggestions, suggestionHint, type ChatSuggestion } from '@/lib/suggestion-row';
import { createPersistedOpenState } from '@/lib/persisted-open-state';

// Maps CTA paths to their corresponding SidebarSection IDs.
const CTA_SECTION_MAP: Record<string, SidebarSection> = {
  '/marketplace': 'marketplace',
  '/apps': 'apps',
};

const openState = createPersistedOpenState('nexus.chat.suggestionsOpenByAgent');

/**
 * Agent-scoped "Suggestions" container above the composer: a single
 * clickable header that expands in place to reveal the full suggestion
 * list. Can stack with `FilesBlock` / `DocumentsFilesBlock` /
 * `PresentationInfoBlock` / `DocumentInfoBlock` and sits flush
 * on the composer input box below the stack: shared border, no gap, via
 * `.chat-composer-header-block` in chat-agent-selector.css. Whichever block
 * actually renders first in the stack (order varies, and siblings can hide
 * themselves) picks up the top border/radius via the `first:` variant, so no
 * component needs to know its position.
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
  const [open, setOpen] = useState(() => (agentId ? openState.load(agentId) : false));
  const chips = useMemo(() => activeSuggestions(suggestions), [suggestions]);

  // Restore the remembered state whenever the agent underneath it changes.
  useEffect(() => {
    setOpen(agentId ? openState.load(agentId) : false);
  }, [agentId]);

  const toggleOpen = () => {
    setOpen((value) => {
      const next = !value;
      if (agentId) openState.save(agentId, next);
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
    <div className="chat-composer-header-block border-x border-b border-border/50 first:rounded-t-2xl first:border-t">
      <button
        type="button"
        className="chat-composer-header-toggle"
        aria-expanded={open}
        onClick={toggleOpen}
      >
        <ChevronRight
          size={12}
          className={cn('chat-composer-header-toggle-chevron shrink-0', open && 'is-open')}
        />
        <span className="chat-composer-header-toggle-label">{chips.length} Suggestions</span>
      </button>
      {open && (
        <ul
          className="chat-slides-composer-list chat-composer-header-list"
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
