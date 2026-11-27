import { describe, expect, it } from 'vitest';
import { ownerHref } from '@/components/access/policies/policy-owners';
import {
  changesFrom,
  choicesOf,
  draftOf,
  featureCellValues,
  featureDescription,
  featureExportRow,
  featurePage,
  featureSearchTexts,
  levelPlan,
  otherPolicies,
  pickableLevels,
  rowNotes,
  shownLevel,
  sortedRows,
  type FeatureAccessState,
  type FeatureRow,
} from './feature-access-model';

const SCOPE = 'abi:nexus:organization/acme/nexus:workspace/ws1';

function row(over: Partial<FeatureRow> & Pick<FeatureRow, 'key' | 'label'>): FeatureRow {
  return {
    choice: 'nobody',
    principals: [],
    policy: null,
    hand_edited: false,
    offered: true,
    held: true,
    editable: true,
    reason: null,
    also: [],
    ...over,
  };
}

const ACCESS = { id: 'pol_access', name: 'Alpha access', owner_scope: SCOPE };
const STATE: Pick<FeatureAccessState, 'access_policy' | 'can'> = {
  access_policy: ACCESS,
  can: { create: true, attach: true, detach: true, widen: true },
};

describe('the draft of a row and the changes a save sends', () => {
  const chat = row({ key: 'chat', label: 'Chat', choice: 'everyone' });
  const files = row({ key: 'files', label: 'Files' });
  const marketplace = row({ key: 'marketplace', label: 'Marketplace' });

  it('starts from what each row holds, and sends nothing while nothing changed', () => {
    expect(draftOf(chat)).toEqual({ choice: 'everyone' });
    expect(changesFrom([chat, files, marketplace], { chat: draftOf(chat), files: { choice: 'nobody' } })).toEqual([]);
  });

  it('sends each changed row in one batch: Everyone or Nobody, never Only…', () => {
    const drafts = { chat: { choice: 'nobody' as const }, files: { choice: 'everyone' as const } };
    expect(changesFrom([chat, files, marketplace], drafts)).toEqual([
      { feature: 'chat', choice: 'nobody' },
      { feature: 'files', choice: 'everyone' },
    ]);
  });

  it('orders rows by name', () => {
    expect(sortedRows([marketplace, files, chat]).map((r) => r.key)).toEqual(['chat', 'files', 'marketplace']);
  });
});

describe('what a row may choose', () => {
  it('an editable row offered here: Everyone and Nobody, no Only…', () => {
    const choices = choicesOf(row({ key: 'chat', label: 'Chat' }));
    expect(choices.map((c) => c.value)).toEqual(['everyone', 'nobody']);
    expect(choices.map((c) => c.enabled)).toEqual([true, true]);
  });

  it('a feature not offered here can only be taken back', () => {
    const choices = choicesOf(row({ key: 'graph', label: 'Graph', offered: false }));
    expect(choices.filter((c) => c.enabled).map((c) => c.value)).toEqual(['nobody']);
  });

  it('a row the API says is not editable: none, whatever the caller is', () => {
    const choices = choicesOf(row({ key: 'chat', label: 'Chat', editable: false, reason: 'No.' }));
    expect(choices.some((c) => c.enabled)).toBe(false);
  });

  it('Nobody says nobody in the workspace uses it, admins included', () => {
    const nobody = choicesOf(row({ key: 'chat', label: 'Chat' })).find((c) => c.value === 'nobody');
    expect(nobody?.hint).toMatch(/admins included/);
  });
});

describe('one Access column: None takes the feature out, any other level puts it in', () => {
  const ALL = ['none', 'read', 'write', 'admin'] as const;

  it('shows None for a feature not offered (Nobody), whatever level is stored, and the level otherwise', () => {
    expect(shownLevel('nobody', 'admin')).toBe('none');
    expect(shownLevel('nobody', null)).toBe('none');
    expect(shownLevel('everyone', 'write')).toBe('write');
    expect(shownLevel('everyone', 'none')).toBe('none');
    expect(shownLevel('everyone', null)).toBeNull();
  });

  it('lets an editable row offered here take every level it has', () => {
    expect(pickableLevels(row({ key: 'chat', label: 'Chat' }), [...ALL])).toEqual([...ALL]);
  });

  it('lets a feature the ceiling does not offer only be taken out, and a read-only row nothing', () => {
    expect(pickableLevels(row({ key: 'graph', label: 'Graph', offered: false }), [...ALL])).toEqual(['none']);
    expect(pickableLevels(row({ key: 'chat', label: 'Chat', editable: false }), [...ALL])).toEqual([]);
  });

  it('saves the choice and the level a pick asks, each only when it changes', () => {
    const rows = [
      row({ key: 'chat', label: 'Chat', choice: 'everyone' }),
      row({ key: 'maps', label: 'Maps' }),
      row({ key: 'files', label: 'Files', choice: 'everyone' }),
      row({ key: 'code', label: 'Code', choice: 'everyone' }),
    ];
    const saved = { chat: 'admin', maps: 'read', files: 'write', code: 'none' } as const;
    expect(
      levelPlan(rows, { chat: 'none', maps: 'read', files: 'read', code: 'write' }, (key) => saved[key as keyof typeof saved])
    ).toEqual({
      // Chat taken out (and capped at None); Maps put in (its level already Read); Files lowered;
      // Code, offered but capped at None, opened to Write.
      features: [
        { feature: 'chat', choice: 'nobody' },
        { feature: 'maps', choice: 'everyone' },
      ],
      levels: { 'feature:chat': 'none', 'feature:files': 'read', 'feature:code': 'write' },
    });
    expect(levelPlan(rows, {}, (key) => saved[key as keyof typeof saved])).toEqual({ features: [], levels: {} });
  });
});

describe('what a row says beside its choice', () => {
  it('not offered: names the access policy, with a link to widen it when IAM lets the caller', () => {
    const graph = row({ key: 'graph', label: 'Graph', offered: false });
    expect(rowNotes(graph, STATE)).toEqual([
      {
        tone: 'warning',
        text: 'Not offered in this workspace: Alpha access does not allow it.',
        href: ownerHref(SCOPE, 'pol_access'),
        link: 'Widen Alpha access',
      },
    ]);
    const [note] = rowNotes(graph, { ...STATE, can: { ...STATE.can, widen: false } });
    expect(note.href).toBeUndefined();
  });

  it('a feature policy changed by hand: read-only, with a link to it', () => {
    const policy = { id: 'pol_chat', name: 'Feature · Chat', owner_scope: SCOPE };
    const chat = row({
      key: 'chat',
      label: 'Chat',
      policy,
      hand_edited: true,
      editable: false,
      reason: 'Feature · Chat was changed on its policy page: change it there.',
    });
    expect(rowNotes(chat, STATE)).toEqual([
      {
        tone: 'info',
        text: 'Feature · Chat was changed on its policy page: read-only here.',
        href: ownerHref(SCOPE, 'pol_chat'),
        link: 'Open it',
      },
    ]);
  });

  it('any other refusal: the API reason, as it says it', () => {
    const chat = row({ key: 'chat', label: 'Chat', editable: false, held: false, reason: 'You do not hold Chat here.' });
    expect(rowNotes(chat, STATE)).toEqual([{ tone: 'info', text: 'You do not hold Chat here.' }]);
    expect(rowNotes(row({ key: 'chat', label: 'Chat' }), STATE)).toEqual([]);
  });
});

describe('the other policies naming a feature', () => {
  it('lists each as also granted or denied, Deny first, linked to its page', () => {
    const chat = row({
      key: 'chat',
      label: 'Chat',
      also: [
        { id: 'pol_mkt', name: 'Marketplace', owner_scope: SCOPE, effect: 'Allow', attached: false },
        { id: 'pol_cf', name: 'Chat + Files', owner_scope: SCOPE, effect: 'Allow', attached: true },
        { id: 'pol_no', name: 'No chat', owner_scope: SCOPE, effect: 'Deny', attached: true },
      ],
    });
    expect(otherPolicies(chat).map(({ text, href }) => ({ text, href }))).toEqual([
      { text: 'Also denied by No chat', href: ownerHref(SCOPE, 'pol_no') },
      { text: 'Also granted by Chat + Files', href: ownerHref(SCOPE, 'pol_cf') },
      { text: 'Also granted by Marketplace (attached nowhere)', href: ownerHref(SCOPE, 'pol_mkt') },
    ]);
  });
});

describe('the features table (as Settings › Users)', () => {
  const chat = row({ key: 'chat', label: 'Chat', choice: 'everyone' });
  const maps = row({ key: 'maps', label: 'Maps' });
  const graph = row({ key: 'graph', label: 'Graph', choice: 'everyone', offered: false });

  it('filters a column on what a row holds: its description, its access (None when not offered)', () => {
    expect(featureCellValues(chat, 'access', 'write')).toEqual(['Write']);
    expect(featureCellValues(maps, 'access', 'admin')).toEqual(['None']);
    expect(featureCellValues(chat, 'access', null)).toEqual([]);
    expect(featureCellValues(maps, 'description')).toEqual([featureDescription('maps')]);
    expect(featureDescription('maps')).not.toBe('');
  });

  it('searches the name, the description and not offered', () => {
    expect(featureSearchTexts(maps).join(' ')).toContain('feeds');
    expect(featureSearchTexts(graph)).toContain('not offered');
    expect(featureSearchTexts(chat)).not.toContain('enabled');
  });

  it('exports a row as the table shows it, and opens each feature on its own page', () => {
    expect(featureExportRow(maps, 'admin')).toEqual(['Maps', 'maps', featureDescription('maps'), 'None', 'Yes']);
    expect(featureExportRow(chat, 'write')[3]).toBe('Write');
    expect(featureExportRow(graph, null)).toEqual(['Graph', 'graph', featureDescription('graph'), '', 'No']);
    expect(featurePage('ws1', 'agents')).toBe('/workspace/ws1/settings/agents');
    expect(featurePage('ws1', 'code')).toBeNull();
  });
});
