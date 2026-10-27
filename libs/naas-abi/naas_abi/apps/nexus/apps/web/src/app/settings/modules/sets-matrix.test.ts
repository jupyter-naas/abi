// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { OrganizationSetView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '../system/system-render';
import { fakeApi } from '../system/access/access-fixtures';
import { catalog, organization, setsView } from './sets-fixtures';
import { NOT_IN_ORGANIZATION, SetsMatrix } from './sets-matrix';
import { ModulesSetsView } from './modules';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const box = (label: string) => document.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`);
const mark = (label: string) => document.querySelector(`[aria-label^="${label}:"]`);
const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as
    | HTMLButtonElement
    | undefined;
const byLabel = (label: string) => document.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);

async function render(over: Partial<Record<string, unknown>> = {}, props: Record<string, unknown> = {}) {
  const onChange = vi.fn();
  const api = fakeApi(over);
  mounted = await mount(SetsMatrix, { api, catalog, organization, onChange, ...props });
  return { onChange, api };
}

describe('SetsMatrix', () => {
  it('has a column for the organization and each workspace, checkboxes only where editable', async () => {
    await render();
    const heads = [...document.querySelectorAll('[data-sets-column]')].map((th) => th.getAttribute('data-sets-column'));
    expect(heads).toEqual(['org-1', 'ws-1', 'ws-2']);
    // The organization and Ops are read-only: marks, no inputs.
    expect(box('acme.people in EDF')).toBeNull();
    expect(mark('acme.people in EDF')?.getAttribute('aria-label')).toBe('acme.people in EDF: included');
    expect(mark('acme.crm in EDF')?.getAttribute('aria-label')).toBe('acme.crm in EDF: not included');
    expect(box('acme.people in Research')?.checked).toBe(true);
    expect(document.body.textContent).toContain('Read only');
  });

  it('shows a module the workspace records but its organization lacks as not effective', async () => {
    await render();
    const crm = box('acme.crm in Research')!;
    expect(crm.checked).toBe(true);
    const cell = crm.closest('td')!;
    expect(cell.className).toContain('sets-matrix-cell-outside');
    expect(cell.getAttribute('title')).toBe(NOT_IN_ORGANIZATION);
    expect(document.body.textContent).toContain('1 entry not in the organization’s set');
  });

  it('shows a workspace that records nothing as its organization’s set', async () => {
    await render();
    expect(mark('acme.people in Ops')?.getAttribute('aria-label')).toBe('acme.people in Ops: included');
    expect(mark('acme.crm in Ops')?.getAttribute('aria-label')).toBe('acme.crm in Ops: not included');
  });

  it('offers a workspace only what its organization has', async () => {
    const editable: OrganizationSetView = {
      ...organization,
      workspaces: [{ ...organization.workspaces[1], editable: true }],
    };
    await render({}, { organization: editable });
    const crm = box('acme.crm in Ops')!;
    expect(crm.checked).toBe(false);
    expect(crm.disabled).toBe(true);
    expect(crm.closest('td')!.getAttribute('title')).toContain('add it to the organization first');
    expect(box('acme.people in Ops')!.disabled).toBe(false);
  });

  it('unchecking one item of a whole module saves its other items', async () => {
    const saved = { ...organization.workspaces[0], set: { modules: [], features: ['chat'] } };
    const putWorkspaceSet = vi.fn().mockResolvedValue(saved);
    const { onChange } = await render({ putWorkspaceSet });
    await mounted!.click(byLabel('Expand acme.people'));
    await mounted!.click(box('acme.people agent Recruiter in Research'));
    expect(box('acme.people in Research')!.indeterminate).toBe(true);
    await mounted!.click(byLabel('Save Research'));
    await mounted!.flush();
    expect(putWorkspaceSet).toHaveBeenCalledWith('org-1', 'ws-1', {
      modules: ['acme.crm', 'agent/acme.people/Coach', 'app/acme.people/*', 'acme_people:ExportReport'],
      features: ['chat'],
    });
    expect(onChange).toHaveBeenCalledWith({ ...organization, workspaces: [saved, organization.workspaces[1]] });
  });

  it('shows the API’s refusal under the column and keeps the draft', async () => {
    const putWorkspaceSet = vi
      .fn()
      .mockRejectedValue(new IamAdminError('Not in the set of organization org-1: acme.crm', 422));
    await render({ putWorkspaceSet });
    await mounted!.click(box('Feature Files in Research'));
    await mounted!.click(byLabel('Save Research'));
    await mounted!.flush();
    expect(document.querySelector('[role="alert"]')?.textContent).toBe(
      'Not in the set of organization org-1: acme.crm',
    );
    expect(byLabel('Save Research')).not.toBeNull();
  });

  it('discards a draft, and resets a column to everything with null parts', async () => {
    const putWorkspaceSet = vi.fn().mockResolvedValue(organization.workspaces[0]);
    await render({ putWorkspaceSet });
    await mounted!.click(box('Feature Chat in Research'));
    expect(box('Feature Chat in Research')!.checked).toBe(false);
    await mounted!.click(byLabel('Discard the changes to Research'));
    expect(box('Feature Chat in Research')!.checked).toBe(true);
    await mounted!.click(button('Reset to everything') ?? null);
    await mounted!.click(byLabel('Save Research'));
    await mounted!.flush();
    expect(putWorkspaceSet).toHaveBeenCalledWith('org-1', 'ws-1', { modules: null, features: null });
  });

  it('highlights the workspace asked for', async () => {
    await render({}, { highlightWorkspace: 'ws-2' });
    const head = document.querySelector('[data-sets-column="ws-2"]')!;
    expect(head.className).toContain('sets-matrix-col-highlight');
    expect(document.querySelector('[data-sets-column="ws-1"]')!.className).not.toContain('highlight');
  });
});

describe('ModulesSetsView', () => {
  it('lists the organizations and opens the only one', async () => {
    const sets = vi.fn().mockResolvedValue(setsView);
    mounted = await mount(ModulesSetsView, { api: fakeApi({ sets }) });
    await mounted.flush();
    expect(sets).toHaveBeenCalledWith();
    expect(document.body.textContent).toContain('EDF');
    expect(document.body.textContent).toContain('Modules: 1 of 2');
    expect(document.querySelector('[data-sets-column="ws-1"]')).not.toBeNull();
  });

  it('says why when the sets cannot be read', async () => {
    const sets = vi.fn().mockRejectedValue(new IamAdminError('You do not have permission to do this.', 403));
    mounted = await mount(ModulesSetsView, { api: fakeApi({ sets }) });
    await mounted.flush();
    expect(document.querySelector('[role="alert"]')?.textContent).toBe('You do not have permission to do this.');
  });
});
