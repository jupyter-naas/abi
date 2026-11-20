import { describe, expect, it } from 'vitest';
import { adminRefusal, workspaceCreateBody } from './workspace-create';

const draft = {
  name: ' Sales ',
  slug: 'sales',
  organizationId: 'acme',
  adminId: 'usr_ann',
  creatorId: 'usr_me',
  group: '',
  description: '',
  primaryColor: '#22c55e',
};

describe('the body of a workspace creation', () => {
  it('names the workspace admin picked, and no owner', () => {
    const body = workspaceCreateBody(draft);
    expect(body).toMatchObject({ name: 'Sales', slug: 'sales', organization_id: 'acme', admin_id: 'usr_ann' });
    expect(body).not.toHaveProperty('owner_id');
  });

  it('defaults the workspace admin to the creator', () => {
    expect(workspaceCreateBody({ ...draft, adminId: '' }).admin_id).toBe('usr_me');
  });
});

describe('a refusal about the workspace admin', () => {
  it('is shown at the picker: someone outside the organization', () => {
    const detail = 'The workspace admin must be a person of the organization';
    expect(adminRefusal(400, detail)).toBe(detail);
    expect(adminRefusal(400, 'Workspace admin is not a known user')).toBe('Workspace admin is not a known user');
  });

  it('else above the form', () => {
    expect(adminRefusal(400, 'Slug already exists')).toBeNull();
    expect(adminRefusal(403, 'The workspace admin must be a person of the organization')).toBeNull();
  });
});
