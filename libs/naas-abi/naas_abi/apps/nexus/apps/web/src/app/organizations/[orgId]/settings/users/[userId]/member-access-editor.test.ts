// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { CapabilityGroup } from '@/lib/people';
import { MemberAccessEditor } from './member-access-editor';
import type { AccessDraft } from './member-details';

const DRAFT: AccessDraft = {
  orgAdmin: false,
  level: 'viewer',
  workspaces: [{ id: 'ws-sales', admin: false }],
  capabilities: [],
};

const WORKSPACES = [
  { id: 'ws-sales', name: 'Sales' },
  { id: 'ws-audit', name: 'Audit' },
];

const RUNNERS: CapabilityGroup = {
  id: 'grp_runners',
  name: 'Workflow runners',
  description: null,
  owner_scope: 'abi:nexus:organization/acme',
  scope: 'organization',
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function editor(draft: AccessDraft = DRAFT, props: { disabled?: boolean } = {}) {
  const onChange = vi.fn();
  const loadCapabilities = vi.fn().mockResolvedValue([RUNNERS]);
  mounted = await mount(MemberAccessEditor, {
    orgId: 'acme',
    draft,
    onChange,
    workspaces: WORKSPACES,
    loadCapabilities,
    ...props,
  });
  await mounted.flush();
  return { onChange, loadCapabilities };
}

const q = (selector: string) => mounted!.host.querySelector(selector);
const box = (label: string) => q(`input[aria-label="${label}"]`) as HTMLInputElement | null;

describe('MemberAccessEditor', () => {
  it('shows org admin, the level with its note, each workspace with admin, and the capability groups', async () => {
    const { loadCapabilities } = await editor();
    expect((q('[data-field="org-admin"] input') as HTMLInputElement).checked).toBe(false);
    expect((q('[data-field="level"]') as HTMLSelectElement).value).toBe('viewer');
    expect(q('[data-level-note]')?.textContent).toBe("A level applies in all of this person's workspaces.");
    expect([...mounted!.host.querySelectorAll('[data-workspace]')].map((r) => r.getAttribute('data-workspace'))).toEqual([
      'ws-audit',
      'ws-sales',
    ]);
    expect(box('Works in Sales')?.checked).toBe(true);
    expect(box('Admin of Audit')?.disabled).toBe(true);
    expect(loadCapabilities).toHaveBeenCalledWith({ organizationId: 'acme' });
    expect(q('[data-capability="grp_runners"]')).not.toBeNull();
  });

  it('edits the draft: org admin, level, a workspace and its admin, a capability group', async () => {
    const { onChange } = await editor();
    await mounted!.click(q('[data-field="org-admin"] input'));
    expect(onChange).toHaveBeenLastCalledWith({ ...DRAFT, orgAdmin: true });
    await mounted!.select(q('[data-field="level"]'), 'member');
    expect(onChange).toHaveBeenLastCalledWith({ ...DRAFT, level: 'member' });
    await mounted!.click(box('Works in Audit'));
    expect(onChange).toHaveBeenLastCalledWith({
      ...DRAFT,
      workspaces: [...DRAFT.workspaces, { id: 'ws-audit', admin: false }],
    });
    await mounted!.click(box('Admin of Sales'));
    expect(onChange).toHaveBeenLastCalledWith({ ...DRAFT, workspaces: [{ id: 'ws-sales', admin: true }] });
    await mounted!.click(q('[data-capability="grp_runners"]'));
    expect(onChange).toHaveBeenLastCalledWith({ ...DRAFT, capabilities: ['grp_runners'] });
  });

  it('leaves a workspace, and offers no Owner and no role', async () => {
    const { onChange } = await editor();
    await mounted!.click(box('Works in Sales'));
    expect(onChange).toHaveBeenLastCalledWith({ ...DRAFT, workspaces: [] });
    const options = [...mounted!.host.querySelectorAll('[data-field="level"] option')].map((o) => o.textContent);
    expect(options).toEqual(['Member', 'Viewer']);
    expect(mounted!.host.textContent).not.toContain('Owner');
  });

  it('changes nothing when disabled (their own access)', async () => {
    const { onChange } = await editor(DRAFT, { disabled: true });
    expect((q('[data-field="org-admin"] input') as HTMLInputElement).disabled).toBe(true);
    expect((q('[data-field="level"]') as HTMLSelectElement).disabled).toBe(true);
    await mounted!.click(box('Works in Audit'));
    expect(onChange).not.toHaveBeenCalled();
  });
});
