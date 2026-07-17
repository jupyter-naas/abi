'use client';

import { ChevronDown, Bot, User, Cpu, Brain, Sparkles, Zap, Target, Search, Check } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore, type Agent } from '@/stores/agents';
import { useIntegrationsStore } from '@/stores/integrations';
import { useModelsStore, modelDisplayName } from '@/stores/models';
import { useAgentList } from '@/components/ui/dialogs';
import { getApiUrl } from '@/lib/config';

const getApiBase = () => getApiUrl();

// Helper to get logo URL (prefix relative URLs with API base)
const getLogoUrl = (url: string | null): string | undefined => {
  if (!url) return undefined;
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  return `${getApiBase()}${url}`; // Relative URL -> add API base
};

const iconComponents = {
  user: User,
  bot: Bot,
  cpu: Cpu,
  brain: Brain,
  sparkles: Sparkles,
  zap: Zap,
  target: Target,
  search: Search,
};

function AgentIcon({ icon, size = 16 }: { icon: Agent['icon']; size?: number }) {
  const IconComponent = iconComponents[icon] || Sparkles;
  return <IconComponent size={size} />;
}

function AgentAvatar({ agent, size = 16 }: { agent: Agent; size?: number }) {
  if (agent.logoUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img 
        src={getLogoUrl(agent.logoUrl)} 
        alt={agent.name} 
        className="h-full w-full object-cover" 
      />
    );
  }
  return <AgentIcon icon={agent.icon} size={size} />;
}

export function AgentSelector({ compact = false }: { compact?: boolean }) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const { selectedAgent, setSelectedAgent } = useWorkspaceStore();
  const { defaultAgents, customAgents, filteredAgents, enabledAgents } = useAgentList(searchQuery);

  // Prefer Abi as default, fallback to first enabled agent
  const abiAgent = enabledAgents.find((a) => a.name === 'Abi');
  const defaultAgent = abiAgent || enabledAgents[0];
  const selected = enabledAgents.find((a) => a.id === selectedAgent) || defaultAgent;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
        setSearchQuery(''); // Clear search when closing
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Show default on server to prevent hydration mismatch
  const displayAgent = mounted ? selected : defaultAgent;

  if (!displayAgent) {
    return null;
  }

  return (
    <div ref={ref} className="relative">
      {compact ? (
        <button
          type="button"
          onClick={() => setOpen(!open)}
          title={`Agent: ${displayAgent.name}`}
          className={cn(
            'flex h-8 items-center gap-1.5 rounded-full px-2.5 text-sm font-medium transition-colors',
            'text-muted-foreground hover:bg-muted hover:text-foreground',
            open && 'bg-muted text-foreground'
          )}
        >
          <span className="max-w-[120px] truncate">{displayAgent.name}</span>
          <ChevronDown size={13} className={cn('shrink-0 transition-transform', open && 'rotate-180')} />
        </button>
      ) : (
        <button
          onClick={() => setOpen(!open)}
          className={cn(
            'flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
            'hover:bg-primary/10',
            open && 'bg-primary/10'
          )}
        >
          <div className={cn(
            "flex h-6 w-6 items-center justify-center rounded-md overflow-hidden glow-primary-sm",
            displayAgent.logoUrl ? "bg-transparent" : "bg-primary text-primary-foreground"
          )}>
            <AgentAvatar agent={displayAgent} size={16} />
          </div>
          <span>{displayAgent.name}</span>
          <ChevronDown size={14} className={cn('transition-transform', open && 'rotate-180')} />
        </button>
      )}

      {open && (
        <div className={cn(
          'glass-card absolute bottom-full z-50 mb-1 w-72 max-h-80 overflow-y-auto p-1',
          compact ? 'right-0' : 'left-0'
        )}>
          {/* Search input */}
          <div className="p-2 sticky top-0 bg-background/95 backdrop-blur-sm border-b">
            <input
              type="text"
              placeholder="Search agents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              autoFocus
            />
          </div>

          {/* Default agents section */}
          {defaultAgents.length > 0 && (
            <>
              <div className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase">Default Agents</div>
              {defaultAgents.map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => {
                    setSelectedAgent(agent.id, true);
                    setOpen(false);
                    setSearchQuery('');
                  }}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                    'hover:bg-primary/10',
                    selectedAgent === agent.id && 'bg-primary/15 text-primary'
                  )}
                >
                  <div className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-md overflow-hidden",
                    agent.logoUrl ? "bg-transparent" : "bg-primary/10 text-primary"
                  )}>
                    <AgentAvatar agent={agent} size={16} />
                  </div>
                  <div className="text-left flex-1 min-w-0">
                    <div className="font-medium">{agent.name}</div>
                    <div className="text-xs text-muted-foreground truncate">{agent.description}</div>
                  </div>
                </button>
              ))}
            </>
          )}
          
          {/* Custom agents section */}
          {customAgents.length > 0 && (
            <>
              <div className="px-2 py-1 mt-2 text-xs font-semibold text-muted-foreground uppercase border-t border-border pt-2">Custom Agents</div>
              {customAgents.map((agent) => (
                <button
                  key={agent.id}
                  onClick={() => {
                    setSelectedAgent(agent.id, true);
                    setOpen(false);
                    setSearchQuery('');
                  }}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                    'hover:bg-primary/10',
                    selectedAgent === agent.id && 'bg-primary/15 text-primary'
                  )}
                >
                  <div className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-md overflow-hidden",
                    agent.logoUrl ? "bg-transparent" : "bg-primary/10 text-primary"
                  )}>
                    <AgentAvatar agent={agent} size={16} />
                  </div>
                  <div className="text-left flex-1 min-w-0">
                    <div className="font-medium">{agent.name}</div>
                    <div className="text-xs text-muted-foreground truncate">{agent.description}</div>
                  </div>
                </button>
              ))}
            </>
          )}

          {/* No results */}
          {filteredAgents.length === 0 && (
            <div className="px-3 py-6 text-center text-sm text-muted-foreground">
              No agents match "{searchQuery}"
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Read-only model indicator styled like the compact AgentSelector: a pill that
 * opens a dropdown showing the single model used by the currently selected agent.
 * Resolves the model the same way ChatInterface does (agent.modelId overrides the
 * provider's default model).
 */
export function ModelSelector() {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { selectedAgent } = useWorkspaceStore();
  const { getAgent } = useAgentsStore();
  const { providers, getProviderForAgent: getLegacyProviderForAgent } = useIntegrationsStore();
  const { models, fetchModels } = useModelsStore();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Resolve the model for the selected agent (mirrors ChatInterface.getProviderForAgent).
  // An explicit modelId wins; otherwise fall back to the model the backend
  // resolved for the agent (catalog/registry default), then to legacy provider
  // mappings. This is what keeps the pill from showing an empty/"none" model
  // for ABI agents that don't carry an explicit model assignment.
  const agent = getAgent(selectedAgent);
  let model: string | null = null;
  if (agent?.provider) {
    const provider = providers.find((p) => p.type === agent.provider && p.enabled);
    model = agent.modelId || provider?.model || agent.resolvedModelId || null;
  } else if (agent?.providerId) {
    model =
      providers.find((p) => p.id === agent.providerId && p.enabled)?.model ||
      agent.modelId ||
      agent.resolvedModelId ||
      null;
  } else {
    model =
      agent?.modelId ||
      getLegacyProviderForAgent(selectedAgent)?.model ||
      agent?.resolvedModelId ||
      null;
  }

  // Nothing to show until mounted (avoids hydration mismatch) or when no model resolves.
  if (!mounted || !model) {
    return null;
  }

  // Show the human-readable model name (e.g. "Claude Sonnet 5") when the catalog
  // has it; fall back to the raw id (e.g. "claude-sonnet-5") otherwise.
  const modelLabel = modelDisplayName(models, model) ?? model;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        title={`Model: ${modelLabel}`}
        className={cn(
          'flex h-8 items-center gap-1.5 rounded-full px-2.5 text-sm font-medium transition-colors',
          'text-muted-foreground hover:bg-muted hover:text-foreground',
          open && 'bg-muted text-foreground'
        )}
      >
        <span className="max-w-[140px] truncate">{modelLabel}</span>
        <ChevronDown size={13} className={cn('shrink-0 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="glass-card absolute right-0 bottom-full z-50 mb-1 w-64 max-h-80 overflow-y-auto p-1">
          <div className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase">Model</div>
          <div className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm bg-primary/15 text-primary">
            <div className="min-w-0 flex-1 text-left">
              <div className="font-medium truncate">{modelLabel}</div>
              <div className="text-xs text-muted-foreground truncate">Used by {agent?.name ?? 'this agent'}</div>
            </div>
            <Check size={16} className="shrink-0" />
          </div>
        </div>
      )}
    </div>
  );
}
