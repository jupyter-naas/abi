import { describe, expect, it } from 'vitest';
import {
  createUserRequest,
  initialOrganizationId,
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
  level: 'member',
  orgAdmin: false,
  workspaces: [],
  attachedAdmin: false,
  capabilities: [],
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

describe('the workspaces a person joins', () => {
  it('puts the attached workspace first, with its admin toggle, and never twice', () => {
    expect(
      workspaceGrants(
        {
          attachedAdmin: true,
          workspaces: [
            { id: 'ws-research', admin: false },
            { id: 'ws-2', admin: false },
          ],
        },
        RESEARCH
      )
    ).toEqual([
      { id: 'ws-research', admin: true },
      { id: 'ws-2', admin: false },
    ]);
    expect(workspaceGrants({ attachedAdmin: false, workspaces: [{ id: 'ws-2', admin: true }] })).toEqual([
      { id: 'ws-2', admin: true },
    ]);
  });
});

describe('the one request the form sends', () => {
  const orgConfig = { organization: { fixed: ACME }, organizationId: 'org-acme', organizationRoute: true };

  it('refuses an email that is not one', () => {
    expect(createUserRequest(draft({ email: 'bob' }), orgConfig)).toEqual({
      ok: false,
      error: 'Enter a valid email address.',
    });
  });

  it('joins the attached workspace with the level, the admin toggle and the groups (the workspace page)', () => {
    const built = createUserRequest(
      draft({
        name: 'Bob',
        level: 'viewer',
        capabilities: ['grp_pilot'],
        profile: { job_title: 'Analyst', country: '' },
      }),
      { organization: { fixed: ACME }, organizationId: 'org-acme', attachedWorkspace: RESEARCH, organizationRoute: false }
    );
    expect(built).toEqual({
      ok: true,
      request: {
        route: 'workspace',
        workspaceId: 'ws-research',
        body: {
          email: 'bob@example.com',
          name: 'Bob',
          level: 'viewer',
          admin: false,
          capabilities: ['grp_pilot'],
          provider: undefined,
          profile: { job_title: 'Analyst' },
        },
      },
    });
  });

  it('creates into the organization with two workspaces, admin of one (Org settings › Users › New)', () => {
    const built = createUserRequest(
      draft({
        orgAdmin: false,
        workspaces: [
          { id: 'ws-1', admin: true },
          { id: 'ws-2', admin: false },
        ],
        capabilities: ['grp_runners'],
      }),
      orgConfig
    );
    expect(built.ok && built.request).toMatchObject({
      route: 'organization',
      organizationId: 'org-acme',
      body: {
        level: 'member',
        orgAdmin: false,
        workspaces: [
          { id: 'ws-1', admin: true },
          { id: 'ws-2', admin: false },
        ],
        capabilities: ['grp_runners'],
      },
    });
  });

  it('creates an org admin, or someone of the organization alone with no workspace', () => {
    const admin = createUserRequest(draft({ orgAdmin: true }), orgConfig);
    expect(admin.ok && admin.request.body).toMatchObject({ orgAdmin: true, workspaces: [] });
    const alone = createUserRequest(draft({ level: 'viewer' }), orgConfig);
    expect(alone.ok && alone.request.body).toMatchObject({ orgAdmin: false, level: 'viewer', workspaces: [] });
  });

  it('refuses a Viewer who administers a workspace: a workspace admin is a Member', () => {
    const built = createUserRequest(draft({ level: 'viewer', workspaces: [{ id: 'ws-1', admin: true }] }), orgConfig);
    expect(built).toEqual({ ok: false, error: 'A workspace admin is a Member: pick Member, or untick admin.' });
    const attached = createUserRequest(draft({ level: 'viewer', attachedAdmin: true }), {
      ...orgConfig,
      attachedWorkspace: RESEARCH,
      organizationRoute: false,
    });
    expect(attached.ok).toBe(false);
  });

  it('creates in the organization picked when it is selectable', () => {
    const built = createUserRequest(draft(), {
      organization: { choices: [ACME, GLOBEX] },
      organizationId: 'org-globex',
      organizationRoute: true,
    });
    expect(built.ok && built.request).toMatchObject({ route: 'organization', organizationId: 'org-globex' });
    expect(
      createUserRequest(draft(), { organization: { choices: [ACME] }, organizationId: null, organizationRoute: true })
    ).toEqual({ ok: false, error: 'Pick an organization.' });
  });
});
