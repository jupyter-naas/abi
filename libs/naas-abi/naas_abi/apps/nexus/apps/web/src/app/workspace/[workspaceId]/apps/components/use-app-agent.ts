/**
 * Resolve the agent an app declares in its manifest:
 *
 *     "agent_path": "src/osint/agents/OsintAgent.py",
 *     "agent_class": "OsintAgent"
 *
 * The API turns those into an agent registry key (`<python.module>/<ClassName>`)
 * whenever the agent's module is loaded, which is the same identifier stored on
 * every workspace agent row — so the join is normally exact. The looser matches
 * below cover the case where the API could not resolve it (agent registry not
 * built yet) but the workspace still lists the agent.
 */

import { useMemo } from 'react';
import { useAgentsStore, type Agent } from '@/stores/agents';
import type { AppRecord } from './types';

/** Class name implied by a manifest `agent_path` (its file stem). */
export function agentClassFromPath(agentPath: string | null | undefined): string {
  const value = (agentPath ?? '').trim().replace(/\\/g, '/');
  if (!value.endsWith('.py')) return '';
  return value.split('/').pop()!.slice(0, -'.py'.length);
}

const eq = (a: string | null | undefined, b: string | null | undefined) =>
  Boolean(a && b && a.toLowerCase() === b.toLowerCase());

type AppAgentFields = Pick<AppRecord, 'agentPath' | 'agentClass' | 'agentClassName' | 'modulePath'>;

/** The workspace agent an app is bound to, or undefined when there is none. */
export function findAppAgent(
  agents: Agent[],
  record: AppAgentFields | null,
): Agent | undefined {
  if (!record) return undefined;
  const enabled = agents.filter((a) => a.enabled);

  if (record.agentClassName) {
    const exact = enabled.find((a) => eq(a.class_name, record.agentClassName));
    if (exact) return exact;
  }

  const className = (record.agentClass ?? '').trim() || agentClassFromPath(record.agentPath);
  if (!className) return undefined;

  const bySuffix = enabled.filter((a) => eq(a.class_name?.split('/').pop(), className));
  if (bySuffix.length === 1) return bySuffix[0];
  if (bySuffix.length > 1) {
    // Ambiguous class name: prefer the agent shipped by this app's own module.
    const root = record.modulePath?.split('.')[0] ?? '';
    return (
      (root ? bySuffix.find((a) => a.class_name?.startsWith(`${root}.`)) : undefined) ??
      bySuffix[0]
    );
  }

  // Last resort: match the display name, which is the class name with spacing
  // and casing of its own ("OsintAgent" → "Osint Agent").
  const squash = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, '');
  const target = squash(className);
  return enabled.find((a) => squash(a.name) === target);
}

export function useAppAgent(record: AppAgentFields | null): Agent | undefined {
  const agents = useAgentsStore((s) => s.agents);
  return useMemo(() => findAppAgent(agents, record), [agents, record]);
}
