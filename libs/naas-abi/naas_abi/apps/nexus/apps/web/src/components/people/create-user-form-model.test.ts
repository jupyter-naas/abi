import { describe, expect, it } from 'vitest';
import {
  NO_ORG_ROLE,
  createUserRequest,
  effectiveOrgRole,
  initialOrganizationId,
  orgRoleOptions,
  organizationReadOnly,
  selectedOrganization,
  workspaceGrants,
  type CreateUserDraft,
} from './create-user-form-model';

const ACME = { id: 'org-acme', name: 'Acme' };
const GLOBEX = { id: 'org-globex', name: 'Globex' };
const RESEARCH = { id: 'ws-research', name: 'Research' };

const draft = (over: Partial<CreateUserDraft> = {}): CreateUserDraft => ({
  email: 'bob@example.com',
  name: '',
  orgRole: 'member',
  workspaces: [],
  attachedRole: 'member',
  policyIds: [],
  profile: {},
  ...over,
});

describe('the organization of the form', () => {
  it('is fixed and read-only, or picked among choices', () => {
    expect(organizationReadOnly({ fixed: ACME })).toBe(true);
    expect(selectedOrganization({ fixed: ACME }, null)).toEqual(ACME);
    expect(organizationReadOnly({ choices: [ACME, GLOBEX] })).toBe(false);
    expect(selectedOrganization({ choices: [ACME, GLOBEX] }, 'org-globex')).toEqual(GLOBEX);
    expect(selectedOrganization({ choices: [ACME] }, 'org-unknown')).toBeNull();
  });

  it('starts on the initial choice, else the first', () => {
    expect(initialOrganizationId({ fixed: ACME })).toBe('org-acme');
    expect(initialOrganizationId({ choices: [ACME, GLOBEX], initialId: 'org-globex' })).toBe('org-globex');
    expect(initialOrganizationId({ choices: [ACME, GLOBEX], initialId: 'nope' })).toBe('org-acme');
    expect(initialOrganizationId({ choices: [] })).toBeNull();
  });
});

describe('the org role field', () => {
  it('offers "None (workspace access only)" only once a workspace is picked', () => {
    expect(orgRoleOptions(['member', 'admin'], 0)).toEqual(['member', 'admin']);
    expect(orgRoleOptions(['member', 'admin'], 1)).toEqual(['member', 'admin', NO_ORG_ROLE]);
  });

  it('is not there when the form grants no org role (the workspace page)', () => {
    expect(orgRoleOptions([], 1)).toEqual([]);
  });

  it('falls back from None to member once no workspace is left', () => {
    expect(effectiveOrgRole(NO_ORG_ROLE, ['member', 'admin'], 1)).toBe(NO_ORG_ROLE);
    expect(effectiveOrgRole(NO_ORG_ROLE, ['member', 'admin'], 0)).toBe('member');
    expect(effectiveOrgRole('admin', ['member', 'admin'], 0)).toBe('admin');
  });
});

describe('the workspaces a person gets', () => {
  it('puts the attached workspace first, with its role, and never twice', () => {
    expect(
      workspaceGrants(
        { attachedRole: 'viewer', workspaces: [{ id: 'ws-research', role: 'admin' }, { id: 'ws-2', role: 'member' }] },
        RESEARCH
      )
    ).toEqual([
      { id: 'ws-research', role: 'viewer' },
      { id: 'ws-2', role: 'member' },
    ]);
    expect(workspaceGrants({ attachedRole: 'member', workspaces: [{ id: 'ws-2', role: 'member' }] })).toEqual([
      { id: 'ws-2', role: 'member' },
    ]);
  });
});

describe('the one request the form sends', () => {
  it('refuses an email that is not one', () => {
    expect(createUserRequest(draft({ email: 'bob' }), { organization: { fixed: ACME }, organizationId: 'org-acme', orgRoles: ['member'] })).toEqual({
      ok: false,
      error: 'Enter a valid email address.',
    });
  });

  it('creates into the attached workspace with no org role (the workspace page)', () => {
    const built = createUserRequest(
      draft({ name: 'Bob', attachedRole: 'viewer', policyIds: ['pol_graph'], profile: { job_title: 'Analyst', country: '' } }),
      { organization: { fixed: ACME }, organizationId: 'org-acme', attachedWorkspace: RESEARCH, orgRoles: [] }
    );
    expect(built).toEqual({
      ok: true,
      request: {
        route: 'workspace',
        workspaceId: 'ws-research',
        body: {
          email: 'bob@example.com',
          name: 'Bob',
          role: 'viewer',
          policyIds: ['pol_graph'],
          provider: undefined,
          profile: { job_title: 'Analyst' },
        },
      },
    });
  });

  it('creates into the organization with every workspace picked (Org settings › Users › New)', () => {
    const built = createUserRequest(
      draft({ orgRole: 'admin', workspaces: [{ id: 'ws-1', role: 'member' }, { id: 'ws-2', role: 'viewer' }] }),
      { organization: { fixed: ACME }, organizationId: 'org-acme', orgRoles: ['member', 'admin'] }
    );
    expect(built.ok && built.request).toMatchObject({
      route: 'organization',
      organizationId: 'org-acme',
      body: { role: 'admin', workspaces: [{ id: 'ws-1', role: 'member' }, { id: 'ws-2', role: 'viewer' }] },
    });
  });

  it('sends no org role (null) for workspace access only', () => {
    const built = createUserRequest(draft({ orgRole: NO_ORG_ROLE, workspaces: [{ id: 'ws-1', role: 'member' }] }), {
      organization: { fixed: ACME },
      organizationId: 'org-acme',
      orgRoles: ['member', 'admin'],
    });
    expect(built.ok && built.request.body).toMatchObject({ role: null, workspaces: [{ id: 'ws-1', role: 'member' }] });
  });

  it('creates in the organization picked when it is selectable', () => {
    const built = createUserRequest(draft(), {
      organization: { choices: [ACME, GLOBEX] },
      organizationId: 'org-globex',
      orgRoles: ['member'],
    });
    expect(built.ok && built.request).toMatchObject({ route: 'organization', organizationId: 'org-globex' });
    expect(
      createUserRequest(draft(), { organization: { choices: [ACME] }, organizationId: null, orgRoles: ['member'] })
    ).toEqual({ ok: false, error: 'Pick an organization.' });
  });
});
