import { describe, expect, it } from 'vitest';

import type { Agent } from '@/stores/agents';
import { agentClassFromPath, findAppAgent } from './use-app-agent';

function agent(partial: Partial<Agent> & { id: string }): Agent {
  return {
    name: partial.id,
    description: '',
    class_name: null,
    icon: 'sparkles',
    systemPrompt: '',
    providerId: null,
    provider: null,
    modelId: null,
    logoUrl: null,
    enabled: true,
    tools: [],
    capabilities: { memory: false, reasoning: false, vision: false },
    intentMappings: [],
    isDefault: false,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...partial,
  } as Agent;
}

const osint = agent({
  id: 'a-osint',
  name: 'Osint Agent',
  class_name: 'osint.agents.OsintAgent/OsintAgent',
});
const abi = agent({ id: 'a-abi', name: 'Abi', class_name: 'naas_abi.agents.AbiAgent/AbiAgent' });

const OSINT_APP = {
  agentPath: 'src/osint/agents/OsintAgent.py',
  agentClass: 'OsintAgent',
  agentClassName: 'osint.agents.OsintAgent/OsintAgent',
  modulePath: 'osint',
};

describe('agentClassFromPath', () => {
  it.each([
    ['src/osint/agents/OsintAgent.py', 'OsintAgent'],
    ['OsintAgent.py', 'OsintAgent'],
    ['src/osint/agents/OsintAgent', ''],
    ['', ''],
  ])('reads %s as %s', (raw, expected) => {
    expect(agentClassFromPath(raw)).toBe(expected);
  });
});

describe('findAppAgent', () => {
  it('joins on the resolved registry key', () => {
    expect(findAppAgent([abi, osint], OSINT_APP)?.id).toBe('a-osint');
  });

  it('falls back to the class name when the API could not resolve it', () => {
    expect(findAppAgent([abi, osint], { ...OSINT_APP, agentClassName: null })?.id).toBe('a-osint');
  });

  it('falls back to the path stem when only agent_path is declared', () => {
    const found = findAppAgent([abi, osint], {
      ...OSINT_APP,
      agentClass: null,
      agentClassName: null,
    });
    expect(found?.id).toBe('a-osint');
  });

  it('falls back to the display name', () => {
    const nameOnly = agent({ id: 'a-name', name: 'Osint Agent', class_name: null });
    const found = findAppAgent([abi, nameOnly], { ...OSINT_APP, agentClassName: null });
    expect(found?.id).toBe('a-name');
  });

  it('prefers the app module when two agents share a class name', () => {
    const other = agent({
      id: 'a-other',
      name: 'Other Osint',
      class_name: 'demo.agents.OsintAgent/OsintAgent',
    });
    const found = findAppAgent([other, osint], {
      ...OSINT_APP,
      agentClassName: null,
      modulePath: 'osint.apps.osint',
    });
    expect(found?.id).toBe('a-osint');
  });

  it('ignores disabled agents', () => {
    expect(findAppAgent([abi, { ...osint, enabled: false }], OSINT_APP)).toBeUndefined();
  });

  it('returns nothing when the app declares no agent', () => {
    expect(
      findAppAgent([abi, osint], {
        agentPath: null,
        agentClass: null,
        agentClassName: null,
        modulePath: 'osint',
      }),
    ).toBeUndefined();
    expect(findAppAgent([abi, osint], null)).toBeUndefined();
  });
});
