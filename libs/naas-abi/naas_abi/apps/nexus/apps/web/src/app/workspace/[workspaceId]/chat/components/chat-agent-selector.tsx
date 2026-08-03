'use client';

import { Check, ChevronDown, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useAgentList } from '@/components/ui/dialogs';
import { useWorkspaceStore } from '@/stores/workspace';
import type { Agent } from '@/stores/agents';
import './chat-agent-selector.css';

function AutoToggle({
  on,
  onToggle,
  label,
}: {
  on: boolean;
  onToggle: () => void;
  label: string;
}) {
  return (
    <div className="chat-agent-selector-toggle-row">
      <span>{label}</span>
      <button
        type="button"
        className={cn('chat-agent-selector-toggle', on && 'is-on')}
        onClick={onToggle}
        role="switch"
        aria-checked={on}
        aria-label={label}
      >
        <span className="chat-agent-selector-toggle-knob" />
      </button>
    </div>
  );
}

export type ChatAgentSelectorSource = 'chat' | 'pane';

/**
 * Compact agent picker for the chat composer.
 * Panel = Search + Auto toggle + agents list (no dual-panel / model drill-down).
 * Mobile: bottom sheet. Desktop: compact popover above the trigger.
 *
 * `source="pane"` binds to the right AI / compare surface (paneAgent).
 */
export function ChatAgentSelector({
  source = 'chat',
}: {
  source?: ChatAgentSelectorSource;
} = {}) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const isMobile = useIsMobile();
  const isPane = source === 'pane';

  const selectedAgent = useWorkspaceStore((s) =>
    isPane ? s.paneAgent : s.selectedAgent
  );
  const agentExplicitlySelected = useWorkspaceStore((s) =>
    isPane ? s.paneAgentExplicitlySelected : s.agentExplicitlySelected
  );
  const setSelectedAgent = useWorkspaceStore((s) =>
    isPane ? s.setPaneAgent : s.setSelectedAgent
  );
  const clearAgentExplicitSelection = useWorkspaceStore((s) =>
    isPane ? s.clearPaneAgentExplicitSelection : s.clearAgentExplicitSelection
  );
  const { defaultAgents, customAgents, filteredAgents } = useAgentList(searchQuery);

  const enabledAgents = useMemo(
    () => [...defaultAgents, ...customAgents],
    [defaultAgents, customAgents]
  );

  const defaultAgent = useMemo(() => {
    if (isPane) {
      return (
        enabledAgents.find(
          (a) =>
            a.enabled &&
            (a.name === 'Abi' ||
              (typeof a.class_name === 'string' &&
                a.class_name.toLowerCase().includes('abiagent')))
        ) ??
        enabledAgents.find((a) => a.isDefault) ??
        enabledAgents[0]
      );
    }
    return enabledAgents.find((a) => a.isDefault) ?? enabledAgents[0];
  }, [enabledAgents, isPane]);
  const activeAgent =
    enabledAgents.find((a) => a.id === selectedAgent) || defaultAgent;
  const autoMode = !agentExplicitlySelected;

  useEffect(() => {
    setMounted(true);
  }, []);

  const closePicker = useCallback(() => {
    setOpen(false);
    setSearchQuery('');
  }, []);

  useEffect(() => {
    if (!open || isMobile) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        closePicker();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open, isMobile, closePicker]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closePicker();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, closePicker]);

  // Keep the mobile sheet glued to the visual viewport so iOS keyboard focus
  // does not shove the page (fixed bottom is layout-viewport relative on Safari).
  useEffect(() => {
    if (!open || !isMobile) return;
    const sheet = sheetRef.current;
    const vv = window.visualViewport;
    if (!sheet || !vv) return;

    const sync = () => {
      const inset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      sheet.style.bottom = `${inset}px`;
      sheet.style.maxHeight = `${Math.min(vv.height * 0.85, 560)}px`;
    };
    sync();
    vv.addEventListener('resize', sync);
    vv.addEventListener('scroll', sync);
    return () => {
      vv.removeEventListener('resize', sync);
      vv.removeEventListener('scroll', sync);
      sheet.style.bottom = '';
      sheet.style.maxHeight = '';
    };
  }, [open, isMobile]);

  useEffect(() => {
    if (!open || !isMobile) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open, isMobile]);

  const openPicker = () => {
    setOpen(true);
  };

  const handleAutoToggle = () => {
    if (autoMode) {
      if (activeAgent) setSelectedAgent(activeAgent.id, true);
    } else {
      clearAgentExplicitSelection();
      if (defaultAgent) setSelectedAgent(defaultAgent.id, false);
      closePicker();
    }
  };

  const selectAgent = (agent: Agent) => {
    setSelectedAgent(agent.id, true);
    closePicker();
  };

  // Pane surface: always show the resolved agent name (Abi by default).
  // Main chat keeps Cursor-style "Auto" until the user picks an agent.
  const triggerLabel = isPane
    ? activeAgent?.name ?? 'Abi'
    : autoMode
      ? 'Auto'
      : activeAgent?.name ?? 'Agent';

  if (!mounted || !activeAgent) {
    return null;
  }

  const renderAgentRow = (agent: Agent) => {
    const isSelected = selectedAgent === agent.id && !autoMode;

    return (
      <button
        key={agent.id}
        type="button"
        className={cn('chat-agent-selector-row', isSelected && 'is-active')}
        onClick={() => selectAgent(agent)}
      >
        <div className="chat-agent-selector-row-body">
          <div className="chat-agent-selector-row-title">{agent.name}</div>
        </div>
        {isSelected ? <Check size={14} className="chat-agent-selector-check" /> : null}
      </button>
    );
  };

  const agentListPanel = (
    <>
      <div className="chat-agent-selector-search-wrap">
        <input
          type="search"
          className="chat-agent-selector-search"
          placeholder="Search agents..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onClick={(e) => e.stopPropagation()}
          autoComplete="off"
          enterKeyHint="search"
        />
      </div>
      <AutoToggle label="Auto" on={autoMode} onToggle={handleAutoToggle} />
      <div className="chat-agent-selector-scroll">
        {defaultAgents.length > 0 && (
          <>
            <div className="chat-agent-selector-section-label">Agents</div>
            {defaultAgents.map((agent) => renderAgentRow(agent))}
          </>
        )}
        {customAgents.length > 0 && (
          <>
            <div className="chat-agent-selector-section-label">Custom</div>
            {customAgents.map((agent) => renderAgentRow(agent))}
          </>
        )}
        {filteredAgents.length === 0 && (
          <p className="chat-agent-selector-empty">No matches for &ldquo;{searchQuery}&rdquo;</p>
        )}
      </div>
    </>
  );

  const desktopPopover = open && !isMobile && (
    <div className="chat-agent-selector-popover" role="dialog" aria-label="Agent picker">
      {agentListPanel}
    </div>
  );

  const mobileSheet =
    open &&
    isMobile &&
    mounted &&
    createPortal(
      <>
        <button
          type="button"
          className="chat-agent-selector-sheet-backdrop"
          aria-label="Close agent picker"
          onClick={closePicker}
        />
        <div
          ref={sheetRef}
          className="chat-agent-selector-sheet"
          role="dialog"
          aria-modal="true"
          aria-label="Agent picker"
        >
          <div className="chat-agent-selector-sheet-header">
            <h2>Agents</h2>
            <button
              type="button"
              className="chat-agent-selector-sheet-close"
              aria-label="Close"
              onClick={closePicker}
            >
              <X size={18} />
            </button>
          </div>
          {agentListPanel}
        </div>
      </>,
      document.body
    );

  return (
    <div ref={ref} className="chat-composer-selector relative min-w-0">
      <button
        type="button"
        className={cn('chat-agent-selector-trigger', open && 'is-open')}
        onClick={() => (open ? closePicker() : openPicker())}
        title={
          isPane
            ? activeAgent.name
            : autoMode
              ? 'Auto agent selection'
              : activeAgent.name
        }
      >
        <span className="chat-agent-selector-trigger-label">{triggerLabel}</span>
        <ChevronDown
          size={13}
          className={cn('shrink-0 transition-transform', open && 'rotate-180')}
        />
      </button>
      {desktopPopover}
      {mobileSheet}
    </div>
  );
}
