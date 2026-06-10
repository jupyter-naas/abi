'use client';

import { ChevronDown, Bot, User, Cpu, Brain, Sparkles, Zap, Target, Search } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore, type Agent } from '@/stores/agents';
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

export function AgentSelector({
  variant = 'default',
  modulePath,
}: {
  variant?: 'default' | 'inline';
  modulePath?: string;
}) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const { selectedAgent, setSelectedAgent } = useWorkspaceStore();
  const { defaultAgents: allDefaultAgents, customAgents: allCustomAgents, filteredAgents: allFilteredAgents, enabledAgents } = useAgentList(searchQuery);

  // Filter agents to module scope when modulePath is provided
  const filterByModule = (agents: typeof enabledAgents) =>
    modulePath
      ? agents.filter((a) => a.module_path && a.module_path.startsWith(modulePath))
      : agents;

  const defaultAgents = filterByModule(allDefaultAgents);
  const customAgents = filterByModule(allCustomAgents);
  const filteredAgents = filterByModule(allFilteredAgents);

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

  const isInline = variant === 'inline';

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center transition-colors',
          isInline
            ? cn(
                'h-8 max-w-[140px] gap-1.5 rounded-full px-2 text-xs',
                'text-muted-foreground hover:bg-muted hover:text-foreground',
                open && 'bg-workspace-accent/15 text-workspace-accent',
              )
            : cn(
                'gap-2 rounded-lg px-3 py-1.5 text-sm font-medium',
                'hover:bg-primary/10',
                open && 'bg-primary/10',
              ),
        )}
        title={`Agent: ${displayAgent.name}`}
      >
        <div className={cn(
          'flex shrink-0 items-center justify-center overflow-hidden',
          isInline
            ? cn('h-5 w-5 rounded-full', displayAgent.logoUrl ? 'bg-transparent' : 'bg-workspace-accent text-white')
            : cn(
                'h-6 w-6 rounded-md glow-primary-sm',
                displayAgent.logoUrl ? 'bg-transparent' : 'bg-primary text-primary-foreground',
              ),
        )}>
          <AgentAvatar agent={displayAgent} size={isInline ? 14 : 16} />
        </div>
        <span className={cn(isInline && 'truncate')}>{displayAgent.name}</span>
        <ChevronDown
          size={isInline ? 12 : 14}
          className={cn('shrink-0 transition-transform', open && 'rotate-180')}
        />
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
                  type="button"
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
                  type="button"
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
