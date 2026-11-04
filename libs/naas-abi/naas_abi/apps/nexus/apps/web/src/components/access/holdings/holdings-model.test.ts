import { describe, expect, it } from 'vitest';
import { ORG, WS, attachment } from '../access-fixtures';
import { principal } from '../service-fixtures';
import { holdingRows, levelLabel, roleTargetOf } from './holdings-model';

const DEMO = 'abi:nexus:organization/demo-org/nexus:workspace/demo';
const names = { [ORG]: 'Acme', [WS]: 'Sales', 'abi:nexus:organization/demo-org': 'Demo org', [DEMO]: 'Ontology demo' };

describe('levelLabel', () => {
  it('names a level as the Owner column names containers', () => {
    expect(levelLabel('abi:', names)).toBe('Platform');
    expect(levelLabel(ORG, names)).toBe('Organization Acme');
    expect(levelLabel(WS, names)).toBe('Workspace Sales (Acme)');
    expect(levelLabel(`${WS}/dev_people:project/p1`, names)).toBe('Project p1 (Sales, Acme)');
    expect(levelLabel(`${ORG}/*`, names)).toBe('Organization Acme, and all below it');
    expect(levelLabel(null, names)).toBe('Everywhere');
    // Unnamed containers show their ids.
    expect(levelLabel(WS)).toBe('Workspace ws-1 (acme)');
  });
});

describe('roleTargetOf', () => {
  it('reads the membership a role row changes through', () => {
    expect(roleTargetOf(ORG)).toEqual({ level: 'organization', organizationId: 'acme' });
    expect(roleTargetOf(WS)).toEqual({ level: 'workspace', workspaceId: 'ws-1' });
    expect(roleTargetOf(`${ORG}/*`)).toBeNull();
    expect(roleTargetOf('abi:')).toBeNull();
    expect(roleTargetOf(null)).toBeNull();
    expect(roleTargetOf(`${WS}/dev_people:project/p1`)).toBeNull();
  });
});

describe('holdingRows', () => {
  const bob = principal({ id: 'usr_bob', display_name: 'Bob' });
  const g = principal({ id: 'grp_g', kind: 'group', name: 'G', display_name: null, email: null, owner_scope: WS });

  it('lists every role, policy and group grant, from the top level down, roles first', () => {
    const rows = holdingRows(
      [
        attachment({ id: 'a1', policy_id: 'pol_bfo', policy_name: 'Bob: BFO only', principal_id: bob.id, principal: bob, scope: DEMO }),
        attachment({ id: 'a2', policy_id: 'builtin.member', policy_name: 'Member', principal_id: bob.id, principal: bob, scope: WS }),
        attachment({ id: 'a3', policy_id: 'builtin.member', policy_name: 'Member', principal_id: bob.id, principal: bob, scope: ORG }),
        attachment({ id: 'a4', policy_id: 'builtin.platform.member', policy_name: 'Platform member', principal_id: bob.id, principal: bob, scope: null }),
        attachment({ id: 'a5', policy_id: 'pol_x', policy_name: 'Extra', principal_id: bob.id, principal: bob, scope: WS }),
      ],
      [{ group: g, attachments: [attachment({ id: 'a6', policy_id: 'pol_w', policy_name: 'W analysts', principal_id: g.id, principal: g, scope: WS })] }],
    );
    expect(rows.map((r) => r.attachment.id)).toEqual(['a4', 'a3', 'a2', 'a5', 'a6', 'a1']);
    const [companion, orgRole, wsRole, extra, viaGroup] = rows;
    expect(companion).toMatchObject({ role: null, companion: true, via: null });
    expect(orgRole).toMatchObject({ role: 'member', companion: false, via: null });
    expect(wsRole.role).toBe('member');
    expect(extra).toMatchObject({ role: null, companion: false, via: null });
    expect(viaGroup).toMatchObject({ role: null, via: { id: 'grp_g', label: 'G' } });
  });

  it('reads a role only for a user: a group holding builtin.member holds a policy', () => {
    const [row] = holdingRows([attachment({ policy_id: 'builtin.member', principal_id: g.id, principal: g, scope: WS })], []);
    expect(row.role).toBeNull();
  });
});
