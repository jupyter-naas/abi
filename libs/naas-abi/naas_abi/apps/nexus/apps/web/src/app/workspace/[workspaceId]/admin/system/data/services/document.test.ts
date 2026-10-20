// @vitest-environment jsdom
import { createElement, Fragment, type ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { derivedColumns, documentView } from './document';
import {
  checkpointKind,
  checkpointTitle,
  collectionPurpose,
  deriveColumnKeys,
  documentLevel,
  namespaceKind,
  namespaceLabel,
  threadLabel,
  validateDocument,
  validateDocumentId,
} from './document-model';

const doc = (id: string, fields: Record<string, unknown>, attributes: Record<string, string> = {}): ResourceEntry => ({
  id: `acme.module/records/${id}`,
  name: id,
  kind: 'item',
  actions: ['read', 'download', 'write', 'delete'],
  size: null,
  modified: '2026-10-02T10:00:00+00:00',
  attributes: { version: '3', fields: JSON.stringify(fields), keys: String(Object.keys(fields).length), ...attributes },
});

const container = (id: string, name: string, attributes: Record<string, string>): ResourceEntry => ({
  id,
  name,
  kind: 'container',
  actions: id.includes('/') ? ['delete'] : [],
  size: null,
  modified: null,
  attributes,
});

function Node({ node }: { node: ReactNode }) {
  return createElement(Fragment, null, node);
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('document model', () => {
  it('tells namespaces, collections and documents apart by their id', () => {
    expect(documentLevel('acme.module')).toBe('namespace');
    expect(documentLevel('acme.module/records')).toBe('collection');
    expect(documentLevel('acme.module/records/a/b')).toBe('document');
  });

  it('labels module namespaces and well-known collections', () => {
    expect(namespaceLabel('operations.projects.nats_probe.researcher')).toEqual({
      lead: 'researcher',
      context: 'operations.projects.nats_probe',
    });
    expect(namespaceLabel('naas_abi')).toEqual({ lead: 'naas_abi', context: '' });
    expect(namespaceKind('operations.projects.nats_probe.researcher')).toBe('Project');
    expect(namespaceKind('naas_abi')).toBe('Platform');
    expect(namespaceKind('naas_abi_core.dataset')).toBe('Core');
    expect(collectionPurpose('agent_runs_206bba6b1fb4fd72')).toBe('Agent runs');
    expect(collectionPurpose('langgraph_checkpoints_v1')).toBe('LangGraph checkpoints');
    expect(collectionPurpose('langgraph_checkpoints_v2')).toBe('LangGraph checkpoints');
    expect(collectionPurpose('langgraph_items_v2')).toBe('LangGraph values');
    expect(collectionPurpose('records')).toBeNull();
  });

  it('derives columns from the keys most documents share, telling ones first', () => {
    const entries = [
      doc('a', { status: 'done', zeta: 1, title: 'A', rare: true }),
      doc('b', { status: 'open', zeta: 2, title: 'B' }),
      doc('c', { status: null, zeta: 3, title: 'C' }),
    ];
    expect(deriveColumnKeys(entries)).toEqual(['title', 'status', 'zeta']);
    expect(deriveColumnKeys([doc('only', { title: 'x' })])).toEqual([]);
  });

  it('validates documents and ids before saving', () => {
    expect(validateDocument('{"a": 1}')).toBeNull();
    expect(validateDocument('[1, 2]')).toMatch(/JSON object/);
    expect(validateDocument('{"a": ')).toMatch(/Not valid JSON/);
    expect(validateDocument('{"$t": "datetime", "$v": "2026-10-02"}')).toMatch(/tagged value/);
    expect(validateDocument('   ')).toMatch(/JSON object/);
    expect(validateDocumentId(' padded')).toMatch(/spaces/);
    expect(validateDocumentId('runs/2026/10')).toBeNull();
  });
});

describe('document view', () => {
  it('shows namespaces as cards with a readable name and their origin', async () => {
    const level = documentView.level!(0, '');
    const entry = container('operations.projects.nats_probe.researcher', 'operations.projects.nats_probe.researcher', {
      collections: '6',
    });
    mounted = await mount(Node, {
      node: createElement(Fragment, null, level.card!(entry), documentView.badges!(entry), level.columns![0].render(entry)),
    });

    expect(level.layout).toBe('cards');
    expect(mounted.host.querySelector('.data-document-ns-lead')?.textContent).toBe('researcher');
    expect(mounted.host.textContent).toContain('operations.projects.nats_probe');
    expect(mounted.host.textContent).toContain('Project');
    expect(mounted.host.textContent).toContain('6');
  });

  it('lists collections with their purpose and document count', async () => {
    const level = documentView.level!(1, 'naas_abi');
    const entry = container('naas_abi/agent_runs_206bba6b', 'agent_runs_206bba6b', { documents: '1234' });
    mounted = await mount(Node, {
      node: createElement(Fragment, null, documentView.badges!(entry), level.columns![0].render(entry)),
    });

    expect(mounted.host.textContent).toContain('Agent runs');
    expect(mounted.host.textContent).toContain('1,234');
    expect(documentView.nounFor!(entry, 1).one).toBe('collection');
    expect(documentView.deleteWarning!(entry)).toContain('1,234 documents');
  });

  it('shows the fields and indexes each collection declares', async () => {
    const level = documentView.level!(1, 'acme.module');
    const fields = level.columns!.find((c) => c.id === 'fields')!;
    const spec = {
      fields: [
        { name: 'email', type: 'string', indexed: false, unique: true },
        { name: 'age', type: 'int', indexed: true, unique: false },
      ],
      unique_together: [['first', 'last']],
    };
    const people = container('acme.module/people', 'people', {
      documents: '3',
      declared_fields: '2',
      spec: JSON.stringify(spec),
    });
    mounted = await mount(Node, { node: fields.render(people) });

    expect(mounted.host.textContent).toContain('email');
    expect(mounted.host.textContent).toContain('age');
    const title = mounted.host.querySelector('[title]')?.getAttribute('title') ?? '';
    expect(title).toContain('email: string, unique');
    expect(title).toContain('age: int, indexed');
    expect(title).toContain('unique together: first + last');
    await mounted.unmount();

    const plain = container('acme.module/records', 'records', { documents: '1', declared_fields: '0', spec: '{"fields":[],"unique_together":[]}' });
    mounted = await mount(Node, { node: fields.render(plain) });
    expect(mounted.host.textContent).toContain('none declared');
  });

  it('shows documents as key/value chips, with version and derived columns', async () => {
    const entries = [doc('a', { title: 'Alpha', status: 'done', n: 1 }), doc('b', { title: 'Beta', status: 'open', n: 2 })];
    const level = (documentView.level as (d: number, p: string, e?: ResourceEntry[]) => ReturnType<NonNullable<typeof documentView.level>>)(
      2,
      'acme.module/records',
      entries,
    );
    mounted = await mount(Node, {
      node: createElement(
        Fragment,
        null,
        documentView.summary!(entries[0]),
        ...level.columns!.map((c) => createElement('span', { key: c.id }, c.render(entries[0]))),
      ),
    });

    expect(level.columns!.map((c) => c.label)).toEqual(['title', 'status', 'n', 'Version', 'Updated']);
    expect([...mounted.host.querySelectorAll('.data-document-chip-key')].map((n) => n.textContent)).toEqual([
      'title',
      'status',
      'n',
    ]);
    expect(mounted.host.textContent).toContain('Alpha');
    expect(mounted.host.textContent).toContain('v3');
    expect(derivedColumns([])).toEqual([]);
  });

  it('previews a document with its location, version and JSON tree', async () => {
    const detail: ResourceDetail = {
      entry: doc('a', { title: 'Alpha' }, { created_at: '2026-10-01T10:00:00+00:00' }),
      content: { encoding: 'text', text: '{"title": "Alpha"}', size: 18, truncated: false },
      view: { type: 'json', value: { title: 'Alpha', when: { $t: 'datetime', $v: '2026-10-02T08:00:00+00:00' } } },
    };
    mounted = await mount(Node, { node: documentView.preview!(detail, {}) });

    expect(mounted.host.querySelector('.data-document-path')?.textContent).toContain('acme.module');
    expect(mounted.host.querySelector('.data-document-path')?.textContent).toContain('records');
    expect(mounted.host.querySelector('.data-document-meta')?.textContent).toContain('v3');
    expect(mounted.host.querySelector('.json-tree')?.textContent).toContain('"Alpha"');
    expect(mounted.host.querySelector('.json-tree')?.textContent).toContain('datetime');
    expect(documentView.preview!({ ...detail, view: null }, {})).toBeNull();
  });

  it('edits documents as validated JSON', () => {
    const editor = documentView.editor!;
    expect(editor.language('acme.module/records/a')).toBe('json');
    expect(editor.validate!(editor.template!('acme.module/records'))).toBeNull();
    expect(documentView.deleteWarning!(doc('a', {}))).toContain('not found');
  });
});


describe('checkpoint collections', () => {
  const step = (thread: string, attributes: Record<string, string>): ResourceEntry => ({
    id: `acme.agents/langgraph_checkpoints_v2/${thread}-${attributes.step}`,
    name: 'f'.repeat(64),
    kind: 'item',
    actions: ['read', 'download', 'write', 'delete'],
    size: null,
    modified: '2026-10-02T10:00:00+00:00',
    attributes: { thread, agent: 'agent-a', ...attributes },
  });

  it('recognizes saver collections and names rows by step', () => {
    const entry = step('3a52e297b6b9f33593892d3d862c541b', { step: '3', source: 'loop', messages: '5', last: 'ai: Done.' });

    expect(checkpointKind('acme.agents/langgraph_checkpoints_v1')).toBe('checkpoint');
    expect(checkpointKind('acme.agents/langgraph_checkpoints_v2/x')).toBe('checkpoint');
    expect(checkpointKind('acme.agents/langgraph_writes_v1/x')).toBe('write');
    expect(checkpointKind('acme.agents/langgraph_writes_v2')).toBe('write');
    expect(checkpointKind('acme.agents/langgraph_blobs_v2/b-1')).toBeNull();
    expect(checkpointKind('acme.agents/records/x')).toBeNull();
    expect(checkpointTitle(entry)).toBe('Step 3 · loop');
    expect(threadLabel(entry)).toBe('Thread 3a52e297b6b9… · agent-a');
    expect(documentView.title!(entry)).toBe('Step 3 · loop');
    expect(documentView.title!(doc('a', {}))).toBeNull();
    expect(documentView.summary!(entry)).toBe('5 messages · ai: Done.');
  });

  it('lists checkpoints grouped by thread with messages and save time, and no manual create', () => {
    const level = (documentView.level as (d: number, p: string, e?: ResourceEntry[]) => ReturnType<NonNullable<typeof documentView.level>>)(
      2,
      'acme.agents/langgraph_checkpoints_v1',
    );

    expect(level.noun).toEqual({ one: 'checkpoint', many: 'checkpoints' });
    expect(level.columns!.map((c) => c.label)).toEqual(['Messages', 'Saved']);
    expect(level.groupBy!(step('t-1', { step: '1' }))).toBe('Thread t-1 · agent-a');
    expect(documentView.canCreate!(2, 'acme.agents/langgraph_checkpoints_v1')).toMatch(/Agents write checkpoints/);
    expect(documentView.canCreate!(2, 'acme.module/records')).toBe(true);
  });
});
