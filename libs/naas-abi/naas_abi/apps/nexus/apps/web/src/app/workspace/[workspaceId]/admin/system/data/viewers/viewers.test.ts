// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { groupHistory } from '../inspector';
import { mount, type Mounted } from '../../system-render';
import type { CheckpointView as Checkpoint } from '../data-types';
import { hexDump } from './binary-view';
import { CheckpointView, brief } from './checkpoint-view';
import { JsonTree } from './json-tree';
import { parseTerm } from './triples-view';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('viewers', () => {
  it('renders a JSON tree two levels deep and expands the rest', async () => {
    mounted = await mount(JsonTree, {
      value: { name: 'Ada', tags: ['x'], deep: { deeper: { deepest: true } }, when: { $t: 'datetime', $v: '2026-10-02' } },
    });
    const text = () => mounted!.host.textContent ?? '';
    expect(text()).toContain('name');
    expect(text()).toContain('"Ada"');
    expect(text()).toContain('datetime');
    expect(text()).not.toContain('deepest');

    const expand = [...mounted.host.querySelectorAll('button')].find((b) => b.textContent?.includes('Expand all'));
    await mounted.click(expand ?? null);

    expect(text()).toContain('deepest');
  });

  it('parses N-Triples terms', () => {
    expect(parseTerm('<http://x.org/a>')).toEqual({ kind: 'iri', value: 'http://x.org/a' });
    expect(parseTerm('"hello"@en')).toEqual({ kind: 'literal', value: 'hello', lang: 'en', datatype: undefined });
    expect(parseTerm('"1"^^<http://www.w3.org/2001/XMLSchema#int>')).toMatchObject({
      kind: 'literal',
      value: '1',
      datatype: 'http://www.w3.org/2001/XMLSchema#int',
    });
    expect(parseTerm('_:b0').kind).toBe('blank');
  });

  it('dumps bytes as hex with ASCII', () => {
    const [line] = hexDump(new TextEncoder().encode('ABI\u0000'));
    expect(line.startsWith('00000000  41 42 49 00')).toBe(true);
    expect(line.endsWith('ABI·')).toBe(true);
  });

  it('merges requested records with their outcome', () => {
    const base = { actor_id: 'u1', actor: 'Ada', service: 'secret', resource_id: 'K', error: '' };
    const grouped = groupHistory([
      { ...base, at: '3', operation: 'reveal', phase: 'succeeded' },
      { ...base, at: '2', operation: 'reveal', phase: 'requested' },
      { ...base, at: '1', operation: 'replace', phase: 'requested' },
    ]);
    expect(grouped.map((g) => [g.operation, g.outcome])).toEqual([
      ['reveal', 'succeeded'],
      ['replace', 'unknown'],
    ]);
  });
});


const checkpoint: Checkpoint = {
  agent_id: 'nats-probe-orchestrator-v1',
  thread_id: '3a52e297b6b9f33593892d3d862c541b',
  checkpoint_ns: '',
  checkpoint_id: '1f1be493-cfdf-6d2c',
  parent_id: '1f1be493-cfde-6b66',
  parent_entry: 'acme.agents/langgraph_checkpoints_v1/abc',
  created_at: '2026-10-02T10:08:39+00:00',
  step: 3,
  source: 'loop',
  messages: [
    { role: 'system', content: 'You answer briefly.' },
    { role: 'human', content: 'What is JetStream?' },
    {
      role: 'ai',
      content: '',
      model: 'gpt-5.5',
      usage: { input_tokens: 120, output_tokens: 8, total_tokens: 128 },
      tool_calls: [{ id: 'call-1', name: 'Researcher', args: { prompt: 'JetStream' } }],
    },
    { role: 'tool', name: 'Researcher', tool_call_id: 'call-1', content: 'NATS persistence.' },
    { role: 'ai', content: 'x'.repeat(900) },
  ],
  channels: { current_active_agent: 'Researcher' },
  metadata: { source: 'loop', step: 3 },
  writes: [
    { task_id: 't1', task_path: '~__pregel_pull, call_model', channel: 'messages', index: 0, value: [{ role: 'ai', content: 'Partial' }] },
    { task_id: 't1', task_path: '~__pregel_pull, call_model', channel: 'branch:to:tools', index: 1, value: null },
  ],
};

describe('checkpoint view', () => {
  const button = (label: string) =>
    [...mounted!.host.querySelectorAll('button')].find((b) => b.textContent?.trim().startsWith(label)) ?? null;
  const text = () => mounted!.host.textContent ?? '';

  it('reads a checkpoint as a transcript with tool calls, models and tokens', async () => {
    mounted = await mount(CheckpointView, { view: checkpoint });

    const roles = [...mounted.host.querySelectorAll('.ckpt-message-role')].map((n) => n.textContent);
    expect(roles).toEqual(['System', 'User', 'Assistant', 'Tool · Researcher', 'Assistant']);
    expect(text()).toContain('gpt-5.5');
    expect(text()).toContain('120 → 8 tokens');
    expect(mounted.host.querySelector('.ckpt-facts')?.textContent).toContain('128');
    expect(mounted.host.querySelector('.ckpt-call-args')?.textContent).toBe('{"prompt":"JetStream"}');

    await mounted.click(mounted.host.querySelector('.ckpt-call-head'));
    expect(mounted.host.querySelector('.ckpt-call-body')?.textContent).toContain('call-1');

    expect(text()).not.toContain('x'.repeat(900));
    await mounted.click(button('Show all 900 characters'));
    expect(text()).toContain('x'.repeat(900));
  });

  it('shows the other state, the pending writes and the metadata', async () => {
    mounted = await mount(CheckpointView, { view: checkpoint });

    await mounted.click(button('State'));
    expect(mounted.host.querySelector('.json-tree')?.textContent).toContain('current_active_agent');
    await mounted.click(button('Pending writes'));
    expect([...mounted.host.querySelectorAll('.ckpt-write-head')].map((n) => n.textContent)).toEqual([
      'messages~__pregel_pull, call_model',
      'branch:to:tools~__pregel_pull, call_model',
    ]);
    expect(text()).toContain('Partial');
    expect(text()).toContain('No value (a signal for the next step).');
    await mounted.click(button('Metadata'));
    expect(mounted.host.querySelector('.json-tree')?.textContent).toContain('loop');
  });

  it('opens the previous step when it can, and says when there is none', async () => {
    const onOpen = vi.fn();
    mounted = await mount(CheckpointView, { view: checkpoint, onOpen });
    await mounted.click(button('The step before'));
    expect(onOpen).toHaveBeenCalledWith('acme.agents/langgraph_checkpoints_v1/abc');
    await mounted.unmount();

    mounted = await mount(CheckpointView, { view: { ...checkpoint, parent_id: null, parent_entry: null, messages: [] } });
    expect(text()).toContain('First step of the thread');
    expect(text()).toContain('No messages at this step');
  });

  it('shortens long values for one line', () => {
    expect(brief({ a: 1 })).toBe('{"a":1}');
    expect(brief('y'.repeat(100), 10)).toBe(`${'y'.repeat(9)}…`);
  });
});
