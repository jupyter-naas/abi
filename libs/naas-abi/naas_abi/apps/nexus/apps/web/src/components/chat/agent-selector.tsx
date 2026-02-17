'use client';

import { ChevronDown, Bot, User, Cpu, Brain, Sparkles, Zap, Target, Search } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore, type Agent } from '@/stores/agents';
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

function shouldShowTechnicalId(agent: Agent): boolean {
  const normalizedName = agent.name.replace(/[\s_-]+/g, '').toLowerCase();
  const normalizedId = agent.id.replace(/[\s_-]+/g, '').toLowerCase();
  return normalizedName !== normalizedId;
}

export function AgentSelector() {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const { selectedAgent, setSelectedAgent } = useWorkspaceStore();
  const { agents, fetchAgents } = useAgentsStore();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);

  // Filter to only enabled agents
  const enabledAgents = agents.filter(a => a.enabled);
  // Prefer SupervisorAgent as default, fallback to first enabled agent
  const abiAgent = enabledAgents.find(a => a.id === 'abi');
  const defaultAgent = abiAgent || enabledAgents[0];
  const selected = enabledAgents.find((a) => a.id === selectedAgent) || defaultAgent;

  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch agents when workspace changes
  useEffect(() => {
    if (currentWorkspaceId) {
      fetchAgents(currentWorkspaceId);
    }
  }, [currentWorkspaceId, fetchAgents]);

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

  // Filter agents by search query and enabled status
  const filteredAgents = searchQuery.trim()
    ? enabledAgents.filter((a) =>
        a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.description.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : enabledAgents;

  const defaultAgents = filteredAgents.filter(a => a.isDefault).sort((a, b) => a.name.localeCompare(b.name));
  const customAgents = filteredAgents.filter(a => !a.isDefault).sort((a, b) => a.name.localeCompare(b.name));

  // Show default on server to prevent hydration mismatch
  const displayAgent = mounted ? selected : defaultAgent;

  if (!displayAgent) {
    return null;
  }

  return (
    <div ref={ref} className="relative">
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

      {open && (
        <div className="glass-card absolute left-0 bottom-full z-50 mb-1 w-72 max-h-80 overflow-y-auto p-1">
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
                    setSelectedAgent(agent.id);
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
                    <div className="flex items-center gap-2">
                      <div className="font-medium">{agent.name}</div>
                      {shouldShowTechnicalId(agent) && (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                          {agent.id}
                        </span>
                      )}
                    </div>
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
                    setSelectedAgent(agent.id);
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
                    <div className="flex items-center gap-2">
                      <div className="font-medium">{agent.name}</div>
                      {shouldShowTechnicalId(agent) && (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                          {agent.id}
                        </span>
                      )}
                    </div>
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
