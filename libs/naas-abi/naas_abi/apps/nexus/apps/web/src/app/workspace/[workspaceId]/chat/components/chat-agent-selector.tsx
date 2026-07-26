'use client';

import { Check, ChevronDown, ChevronLeft, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useAgentList } from '@/components/ui/dialogs';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore, type Agent } from '@/stores/agents';
import { useIntegrationsStore } from '@/stores/integrations';
import { useModelsStore, modelDisplayName } from '@/stores/models';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import {
  modelOptionHints,
  modelsForAgent,
  parseModelLabel,
  resolveAgentModelId,
  type ModelOption,
} from './chat-agent-selector-utils';
import './chat-agent-selector.css';

type MobileView = 'agents' | 'models' | 'options';

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

function BadgeList({ badges }: { badges: string[] }) {
  if (!badges.length) return null;
  return (
    <span className="chat-agent-selector-badges">
      {badges.map((b) => (
        <span key={b} className="chat-agent-selector-badge">
          {b}
        </span>
      ))}
    </span>
  );
}

function ModelOptionsPanel({
  modelId,
  modelLabel,
}: {
  modelId: string;
  modelLabel: string;
}) {
  const hints = modelOptionHints(modelId, modelLabel);
  const effortLevels = ['Low', 'Medium', 'High', 'Extra High', 'Max'];

  return (
    <>
      <div className="chat-agent-selector-option-group">
        <h4>Options</h4>
        <div className="chat-agent-selector-option-row">
          <span>Thinking</span>
          <span
            className={cn('chat-agent-selector-toggle', hints.thinking && 'is-on')}
            style={{ pointerEvents: 'none' }}
          >
            <span className="chat-agent-selector-toggle-knob" />
          </span>
        </div>
        <div className="chat-agent-selector-option-row">
          <span>Fast</span>
          <span
            className={cn('chat-agent-selector-toggle', hints.fast && 'is-on')}
            style={{ pointerEvents: 'none' }}
          >
            <span className="chat-agent-selector-toggle-knob" />
          </span>
        </div>
      </div>
      <div className="chat-agent-selector-option-group">
        <h4>Effort</h4>
        {effortLevels.map((level) => (
          <div
            key={level}
            className={cn(
              'chat-agent-selector-option-row',
              hints.effort === level && 'is-selected'
            )}
          >
            <span>{level}</span>
            {hints.effort === level ? (
              <Check size={14} className="chat-agent-selector-check" />
            ) : null}
          </div>
        ))}
      </div>
      <p className="chat-agent-selector-empty">
        Options reflect model metadata. Context size is not configured in the backend yet.
      </p>
    </>
  );
}

/**
 * Unified agent + model picker for the chat composer.
 * Mobile: bottom sheet with agents → models → options drill-down.
 * Desktop: anchored popover with agent list + side panel for models/options.
 */
export function ChatAgentSelector() {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [focusedAgentId, setFocusedAgentId] = useState<string | null>(null);
  const [focusedModel, setFocusedModel] = useState<ModelOption | null>(null);
  const [mobileView, setMobileView] = useState<MobileView>('agents');
  const [providerModels, setProviderModels] = useState<Array<{ id: string; name: string }>>([]);
  const ref = useRef<HTMLDivElement>(null);
  const isMobile = useIsMobile();

  const {
    selectedAgent,
    agentExplicitlySelected,
    setSelectedAgent,
    clearAgentExplicitSelection,
  } = useWorkspaceStore();
  const { updateAgent } = useAgentsStore();
  const { providers, getProviderForAgent } = useIntegrationsStore();
  const { models, fetchModels } = useModelsStore();
  const { defaultAgents, customAgents, filteredAgents } = useAgentList(searchQuery);

  const enabledAgents = useMemo(
    () => [...defaultAgents, ...customAgents],
    [defaultAgents, customAgents]
  );

  const defaultAgent = enabledAgents.find((a) => a.isDefault) ?? enabledAgents[0];
  const activeAgent =
    enabledAgents.find((a) => a.id === selectedAgent) || defaultAgent;
  const autoMode = !agentExplicitlySelected;

  const activeModelId = resolveAgentModelId(activeAgent, providers, getProviderForAgent);
  const activeModelLabel = activeModelId
    ? modelDisplayName(models, activeModelId) ?? activeModelId
    : null;
  const activeModelParsed = activeModelLabel
    ? parseModelLabel(activeModelLabel)
    : null;

  const focusedAgent = focusedAgentId
    ? enabledAgents.find((a) => a.id === focusedAgentId)
    : activeAgent;

  const focusedModelOptions = useMemo(() => {
    if (!focusedAgent) return [];
    return modelsForAgent(focusedAgent, models, providerModels);
  }, [focusedAgent, models, providerModels]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch(`${getApiUrl()}/api/providers/available`);
        if (!res.ok) return;
        const data: Array<{ models?: Array<{ id: string; name: string }> }> = await res.json();
        if (cancelled) return;
        const merged = new Map<string, { id: string; name: string }>();
        for (const p of data) {
          for (const m of p.models ?? []) {
            if (m.id) merged.set(m.id, m);
          }
        }
        setProviderModels(Array.from(merged.values()));
      } catch {
        /* catalog fallback only */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  const closePicker = useCallback(() => {
    setOpen(false);
    setSearchQuery('');
    setFocusedAgentId(null);
    setFocusedModel(null);
    setMobileView('agents');
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
    if (!open || !isMobile) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closePicker();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, isMobile, closePicker]);

  const openPicker = () => {
    setFocusedAgentId(activeAgent?.id ?? null);
    const modelId = activeAgent
      ? resolveAgentModelId(activeAgent, providers, getProviderForAgent)
      : null;
    if (modelId && activeAgent) {
      const opts = modelsForAgent(activeAgent, models, providerModels);
      setFocusedModel(opts.find((m) => m.id === modelId) ?? null);
    }
    setOpen(true);
  };

  const handleAutoToggle = () => {
    if (autoMode) {
      if (activeAgent) setSelectedAgent(activeAgent.id, true);
    } else {
      clearAgentExplicitSelection();
      if (defaultAgent) setSelectedAgent(defaultAgent.id, false);
    }
  };

  const focusAgent = (agent: Agent) => {
    setFocusedAgentId(agent.id);
    const modelId = resolveAgentModelId(agent, providers, getProviderForAgent);
    const opts = modelsForAgent(agent, models, providerModels);
    const current = modelId ? opts.find((m) => m.id === modelId) : opts[0];
    setFocusedModel(current ?? null);
  };

  const selectAgent = (agent: Agent, navigateModels = false) => {
    setSelectedAgent(agent.id, true);
    focusAgent(agent);
    if (navigateModels) {
      setMobileView('models');
    }
  };

  const selectModel = async (agent: Agent, model: ModelOption) => {
    setSelectedAgent(agent.id, true);
    setFocusedModel(model);
    if (agent.modelId !== model.id) {
      await updateAgent(agent.id, { modelId: model.id });
    }
    if (isMobile) {
      setMobileView('options');
    }
  };

  const triggerLabel = autoMode
    ? 'Auto'
    : activeModelParsed?.title && focusedModelOptions.length > 1
      ? `${activeAgent?.name ?? 'Agent'} · ${activeModelParsed.title}`
      : activeAgent?.name ?? 'Agent';
  const triggerBadge =
    !autoMode && activeModelParsed?.badges.length
      ? activeModelParsed.badges[0]
      : null;

  if (!mounted || !activeAgent) {
    return null;
  }

  const renderAgentRow = (agent: Agent, showModelSubtitle = true) => {
    const modelId = resolveAgentModelId(agent, providers, getProviderForAgent);
    const modelLabel = modelId ? modelDisplayName(models, modelId) ?? modelId : '';
    const parsed = modelLabel ? parseModelLabel(modelLabel) : null;
    const isSelected = selectedAgent === agent.id && !autoMode;
    const isFocused = focusedAgentId === agent.id;

    return (
      <button
        key={agent.id}
        type="button"
        className={cn('chat-agent-selector-row', (isSelected || isFocused) && 'is-active')}
        onClick={() => selectAgent(agent, isMobile)}
        onMouseEnter={() => {
          if (!isMobile) focusAgent(agent);
        }}
      >
        <div className="chat-agent-selector-row-body">
          <div className="chat-agent-selector-row-title">{agent.name}</div>
          {showModelSubtitle && parsed ? (
            <div className="chat-agent-selector-row-sub">{parsed.title}</div>
          ) : null}
        </div>
        <BadgeList badges={parsed?.badges ?? []} />
        {isSelected ? <Check size={14} className="chat-agent-selector-check" /> : null}
      </button>
    );
  };

  const renderModelRow = (model: ModelOption, agent: Agent) => {
    const currentId = resolveAgentModelId(agent, providers, getProviderForAgent);
    const isSelected = currentId === model.id && selectedAgent === agent.id;

    return (
      <button
        key={model.id}
        type="button"
        className={cn('chat-agent-selector-row', isSelected && 'is-active')}
        onClick={() => {
          void selectModel(agent, model);
          if (!isMobile) closePicker();
        }}
        onMouseEnter={() => setFocusedModel(model)}
        onFocus={() => setFocusedModel(model)}
      >
        <div className="chat-agent-selector-row-body">
          <div className="chat-agent-selector-row-title">{model.label}</div>
        </div>
        <BadgeList badges={model.badges} />
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

  const detailPanel = focusedAgent ? (
    <>
      <div className="chat-agent-selector-section-label">
        {focusedAgent.name}
      </div>
      <div className="chat-agent-selector-scroll">
        {focusedModelOptions.length > 0 ? (
          focusedModelOptions.map((model) => renderModelRow(model, focusedAgent))
        ) : (
          <p className="chat-agent-selector-empty">No models configured for this agent.</p>
        )}
      </div>
      {focusedModel && focusedModelOptions.length > 0 ? (
        <ModelOptionsPanel modelId={focusedModel.id} modelLabel={focusedModel.label} />
      ) : null}
    </>
  ) : (
    <p className="chat-agent-selector-empty">Select an agent to view models.</p>
  );

  const desktopPopover = open && !isMobile && (
    <div className="chat-agent-selector-popover">
      <div className="chat-agent-selector-panel chat-agent-selector-panel-list">
        {agentListPanel}
      </div>
      <div className="chat-agent-selector-panel chat-agent-selector-panel-detail">
        {detailPanel}
      </div>
    </div>
  );

  const mobileSheet = open && isMobile && mounted && createPortal(
    <>
      <button
        type="button"
        className="chat-agent-selector-sheet-backdrop"
        aria-label="Close model picker"
        onClick={closePicker}
      />
      <div className="chat-agent-selector-sheet" role="dialog" aria-modal="true" aria-label="Model picker">
        <div className="chat-agent-selector-sheet-header">
          {mobileView !== 'agents' ? (
            <button
              type="button"
              className="chat-agent-selector-sheet-back"
              onClick={() => {
                if (mobileView === 'options') setMobileView('models');
                else setMobileView('agents');
              }}
            >
              <ChevronLeft size={16} className="inline" /> Back
            </button>
          ) : (
            <h2>Model</h2>
          )}
          {mobileView !== 'agents' ? (
            <h2>
              {mobileView === 'models'
                ? focusedAgent?.name ?? 'Models'
                : focusedModel?.label ?? 'Options'}
            </h2>
          ) : null}
          <button
            type="button"
            className="chat-agent-selector-sheet-close"
            aria-label="Close"
            onClick={closePicker}
          >
            <X size={18} />
          </button>
        </div>
        {mobileView === 'agents' && agentListPanel}
        {mobileView === 'models' && focusedAgent && (
          <div className="chat-agent-selector-scroll">
            {focusedModelOptions.map((model) => renderModelRow(model, focusedAgent))}
          </div>
        )}
        {mobileView === 'options' && focusedModel && (
          <div className="chat-agent-selector-scroll">
            <ModelOptionsPanel modelId={focusedModel.id} modelLabel={focusedModel.label} />
          </div>
        )}
        {mobileView === 'options' && (
          <div className="chat-agent-selector-sheet-done">
            <button
              type="button"
              className="chat-agent-selector-row is-active"
              style={{ justifyContent: 'center', width: '100%' }}
              onClick={closePicker}
            >
              Done
            </button>
          </div>
        )}
      </div>
    </>,
    document.body
  );

  return (
    <div ref={ref} className="chat-composer-selector relative min-w-0 max-w-full">
      <button
        type="button"
        className={cn('chat-agent-selector-trigger', open && 'is-open')}
        onClick={() => (open ? closePicker() : openPicker())}
        title={
          autoMode
            ? 'Auto agent selection'
            : `${activeAgent.name}${activeModelLabel ? ` · ${activeModelLabel}` : ''}`
        }
      >
        <span className="chat-agent-selector-trigger-label">{triggerLabel}</span>
        {triggerBadge ? (
          <span className="chat-agent-selector-trigger-badge">{triggerBadge}</span>
        ) : null}
        <ChevronDown size={13} className={cn('shrink-0 transition-transform', open && 'rotate-180')} />
      </button>
      {desktopPopover}
      {mobileSheet}
    </div>
  );
}
