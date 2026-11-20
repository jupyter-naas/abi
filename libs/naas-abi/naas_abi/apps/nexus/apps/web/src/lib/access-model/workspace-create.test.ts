import { describe, expect, it } from 'vitest';
import { workspaceCreateBody } from './workspace-create';

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
