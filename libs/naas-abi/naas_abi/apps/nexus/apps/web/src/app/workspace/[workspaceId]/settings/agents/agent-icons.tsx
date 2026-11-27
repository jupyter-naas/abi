import { Bot, Brain, Cpu, Search, Sparkles, Target, User, Zap } from 'lucide-react';
import { getLogoUrl } from '@/lib/logo-url';
import type { Agent } from '@/stores/agents';

/** The icons an agent the workspace builds may wear, by name. */
export const AGENT_ICONS = {
  bot: Bot,
  user: User,
  cpu: Cpu,
  brain: Brain,
  sparkles: Sparkles,
  zap: Zap,
  target: Target,
  search: Search,
};

export const AGENT_ICON_OPTIONS: Agent['icon'][] = ['user', 'bot', 'cpu', 'brain', 'sparkles', 'zap', 'target', 'search'];

/** An agent's picture: its logo, else its icon. */
export function AgentAvatar({ agent, size = 18 }: { agent: Agent; size?: number }) {
  if (agent.logoUrl) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={getLogoUrl(agent.logoUrl)} alt={agent.name} className="h-full w-full object-cover" />;
  }
  const Icon = AGENT_ICONS[agent.icon] || Sparkles;
  return <Icon size={size} />;
}
