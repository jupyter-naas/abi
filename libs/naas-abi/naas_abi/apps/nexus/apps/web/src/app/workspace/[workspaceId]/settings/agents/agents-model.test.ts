import { describe, expect, it } from 'vitest';
import type { Agent } from '@/stores/agents';
import {
  agentCellValues,
  agentExportRow,
  agentModelIds,
  agentRows,
  agentSearchTexts,
  agentItemFor,
  builtHere,
  type AgentProvider,
} from './agents-model';
import type { ModuleItem } from '@/components/settings/module-items-model';

function agent(over: Partial<Agent> & Pick<Agent, 'id' | 'name'>): Agent {
  return {
    description: '',
    class_name: null,
    icon: 'bot',
    systemPrompt: '',
    providerId: null,
    provider: null,
    modelId: null,
    resolvedModelId: null,
    logoUrl: null,
    tools: [],
    capabilities: { memory: false, reasoning: false, vision: false },
    intentMappings: [],
    isDefault: false,
    createdAt: new Date(0),
    updatedAt: new Date(0),
    ...over,
  };
}

const OPENAI: AgentProvider = { id: 'prov-openai', type: 'openai', enabled: true, model: 'gpt-4o' };
const label = (id: string) => (id === 'gpt-4o' ? 'GPT-4o' : id);

describe('the models an agent shows', () => {
  it('the ones its class declares, once each', () => {
    expect(agentModelIds(agent({ id: 'a', name: 'A', modelIds: [' m1 ', 'm2', 'm1', ''] }), [])).toEqual(['m1', 'm2']);
  });

  it('else its model, its provider model, or the one it resolves to', () => {
    expect(agentModelIds(agent({ id: 'a', name: 'A', provider: 'openai' }), [OPENAI])).toEqual(['gpt-4o']);
    expect(agentModelIds(agent({ id: 'a', name: 'A', provider: 'openai', modelId: 'o3' }), [OPENAI])).toEqual(['o3']);
    expect(agentModelIds(agent({ id: 'a', name: 'A', providerId: 'prov-openai', modelId: 'o3' }), [OPENAI])).toEqual([
      'gpt-4o',
    ]);
    expect(agentModelIds(agent({ id: 'a', name: 'A', provider: 'abi', resolvedModelId: 'qwen' }), [OPENAI])).toEqual([
      'qwen',
    ]);
    expect(agentModelIds(agent({ id: 'a', name: 'A' }), [OPENAI])).toEqual([]);
  });
});

describe('the agents table (as Settings › Users)', () => {
  const rows = agentRows(
    [
      agent({
        id: 'w',
        name: 'Writer',
        description: 'Writes reports',
        class_name: 'naas_abi.agents/WriterAgent',
        provider: 'openai',
      }),
      agent({ id: 'a', name: 'Abi', provider: 'abi' }),
      agent({ id: 'n', name: 'Nobody' }),
    ],
    [OPENAI],
    label,
  );
  const [abi, nobody, writer] = rows;

  it('orders the rows by name and names each model', () => {
    expect(rows.map((row) => row.agent?.id)).toEqual(['a', 'n', 'w']);
    expect(writer.models).toEqual([{ id: 'gpt-4o', label: 'GPT-4o' }]);
  });

  it('filters the Models column on the model names, or why an agent has none', () => {
    expect(agentCellValues(writer, 'agent')).toEqual(['Writer']);
    expect(agentCellValues(writer, 'models')).toEqual(['GPT-4o']);
    expect(agentCellValues(nobody, 'models')).toEqual(['Not assigned']);
    expect(agentCellValues(abi, 'models')).toEqual(['Not exposed']);
  });

  it('searches the name, description, module and models', () => {
    expect(agentSearchTexts(writer)).toEqual(['Writer', 'Writes reports', 'naas_abi.agents', 'GPT-4o']);
  });

  it('exports a row as the table shows it', () => {
    expect(agentExportRow(writer)).toEqual(['Writer', 'naas_abi.agents', 'Writes reports', 'GPT-4o', 'Enabled']);
    expect(agentExportRow(nobody)).toEqual(['Nobody', '', '', 'Not assigned', 'Enabled']);
  });
});

describe('the agents table and the module items', () => {
  const item = (module: string, name: string, offered: boolean): ModuleItem => ({
    kind: 'agents',
    module,
    name,
    label: name,
    offered,
    grantable: true,
  });
  const ITEMS = [
    item('acme.people', 'Coach', true),
    item('acme.people', 'Recruiter', false),
    item('acme', 'Coach', true),
    { ...item('acme.people', 'sync', true), kind: 'workflows' as const },
  ];
  const coach = agent({ id: 'c', name: 'Coach', class_name: 'acme.people.agents.CoachAgent/CoachAgent' });
  const remote = agent({ id: 'r', name: 'Scout', class_name: 'acme.remote/Scout', provider: 'remote' });
  const built = agent({ id: 'b', name: 'Builder' });

  it('finds the item of a module agent: its module or a package of it, the closest, by name or class', () => {
    expect(agentItemFor(coach, ITEMS)).toBe(ITEMS[0]);
    expect(agentItemFor(agent({ id: 'x', name: 'X', class_name: 'acme.people/Coach' }), ITEMS)).toBe(ITEMS[0]);
    expect(agentItemFor(remote, ITEMS)).toBeNull();
    expect(agentItemFor(built, ITEMS)).toBeNull();
  });

  it('lists every module agent: those the roster holds keep their row, the others get one', () => {
    const rows = agentRows([coach, built], [], label, ITEMS);
    expect(rows.map((row) => [row.key, row.agent?.id ?? null, row.item?.name ?? null])).toEqual([
      ['b', 'b', null],
      ['c', 'c', 'Coach'],
      ['agents|acme|Coach', null, 'Coach'],
      ['agents|acme.people|Recruiter', null, 'Recruiter'],
    ]);
    const recruiter = rows[3];
    expect(recruiter.module).toBe('acme.people');
    expect(agentCellValues(recruiter, 'models')).toEqual([]);
    expect(agentCellValues(recruiter, 'enabled')).toEqual(['Disabled']);
    expect(agentCellValues(rows[1], 'enabled')).toEqual(['Enabled']);
    expect(builtHere(rows[0])).toBe(true);
    expect(agentCellValues(rows[0], 'enabled')).toEqual(['Enabled']);
    expect(builtHere(rows[1])).toBe(false);
    expect(builtHere(recruiter)).toBe(false);
    expect(agentExportRow(recruiter)).toEqual(['Recruiter', 'acme.people', '', '', 'Disabled']);
  });
});
