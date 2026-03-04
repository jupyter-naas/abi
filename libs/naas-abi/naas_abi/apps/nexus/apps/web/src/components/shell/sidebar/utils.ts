import {
  User, Bot, Cpu, Brain, Sparkles, Zap, Target, Search,
  Globe, Shield, BookOpen, MessageSquare, FileCode, GitBranch, Network, Users,
  type LucideIcon,
} from 'lucide-react';
import type { Agent } from '@/stores/agents';

/** Generate workspace-scoped URL paths */
export const getWorkspacePath = (workspaceId: string | null, path: string) =>
  workspaceId ? `/workspace/${workspaceId}${path}` : path;

/** Agent icon components mapped by agent icon key */
export const agentIconComponents: Record<Agent['icon'], React.ElementType> = {
  user: User,
  bot: Bot,
  cpu: Cpu,
  brain: Brain,
  sparkles: Sparkles,
  zap: Zap,
  target: Target,
  search: Search,
};

/** Icon map for search sources */
export const searchIconMap: Record<string, LucideIcon> = {
  Globe,
  Shield,
  Search,
  BookOpen,
  MessageSquare,
  FileCode,
  GitBranch,
  Network,
  Users,
};
