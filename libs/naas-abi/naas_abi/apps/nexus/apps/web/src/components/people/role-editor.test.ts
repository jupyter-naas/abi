// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { readRoleOptions, type RoleSelection } from '@/lib/member-roles';
import { RoleEditor } from './role-editor';

const OPTIONS = readRoleOptions({
  groups: [
    { kind: 'level', id: 'grp_m', name: 'Members', level: 'member' },
    { kind: 'level', id: 'grp_v', name: 'Viewers', level: 'viewer' },
    { kind: 'workspace', id: 'grp_w', name: 'ABI workspace' },
    { kind: 'admins', id: 'grp_wa', name: 'ABI admins' },
  ],
  policies: [{ kind: 'policy', id: 'pol_a', name: 'Alpha reports' }],
});

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function render(value: RoleSelection) {
  const onChange = vi.fn();
  mounted = await mount(RoleEditor, { options: OPTIONS, value, onChange });
  return onChange;
}

describe('the Role editor', () => {
  it('shows the workspace group first, fixed, then the others, removable', async () => {
    const onChange = await render({ groups: ['grp_m', 'grp_w', 'grp_hidden'], policies: ['pol_a'] });
    const tags = [...mounted!.host.querySelectorAll('[data-role]')].map((t) => t.textContent);
    expect(tags).toEqual(['ABI workspace', 'Members', 'Alpha reports']);
    expect(mounted!.host.querySelector('[data-role="workspace"] button')).toBeNull();
    await mounted!.click(mounted!.host.querySelector('[data-role="level"] button'));
    // An id the caller is not offered stays.
    expect(onChange).toHaveBeenCalledWith({ groups: ['grp_w', 'grp_hidden'], policies: ['pol_a'] });
  });

  it('adds what is picked, a level in place of the other', async () => {
    const onChange = await render({ groups: ['grp_w', 'grp_m'], policies: [] });
    await mounted!.select(mounted!.host.querySelector('[data-field="add-role"]'), 'level:grp_v');
    expect(onChange).toHaveBeenCalledWith({ groups: ['grp_w', 'grp_v'], policies: [] });
  });

  it('says what would be refused', async () => {
    await render({ groups: ['grp_w'], policies: [] });
    expect(mounted!.host.querySelector('[data-role-problem]')?.textContent).toMatch(/use nothing/);
  });
});
