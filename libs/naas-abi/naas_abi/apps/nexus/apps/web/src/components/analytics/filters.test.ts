// @vitest-environment jsdom
import { act } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { WorkspaceFilter } from './filters';
import { ALL } from './scope';

const WORKSPACES = [
  { workspace_id: 'ws-2', workspace_name: 'Ops' },
  { workspace_id: 'ws-1', workspace_name: 'Finance' },
  { workspace_id: 'ws-3', workspace_name: 'Legal' },
];

let mounted: Mounted | null = null;

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function open(onChange = vi.fn()) {
  mounted = await mount(WorkspaceFilter, { value: ALL, onChange, workspaces: WORKSPACES });
  const trigger = mounted.host.querySelector('button[aria-haspopup="dialog"]') as HTMLButtonElement;
  await mounted.click(trigger);
  return { trigger, onChange, m: mounted };
}

const optionLabels = (host: HTMLElement) =>
  Array.from(host.querySelectorAll('[role="dialog"] button')).map((b) => b.textContent);

describe('WorkspaceFilter', () => {
  it('lists the workspaces by name under "All workspaces", and searches them', async () => {
    const { m } = await open();
    expect(optionLabels(m.host)).toEqual(['All workspaces3', 'Finance', 'Legal', 'Ops']);
    await m.type(m.host.querySelector('input[aria-label="Search workspaces"]'), 'le');
    expect(optionLabels(m.host)).toEqual(['All workspaces3', 'Legal']);
  });

  it('picks a workspace and hands the focus back to its button', async () => {
    const { trigger, onChange, m } = await open();
    const ops = Array.from(m.host.querySelectorAll('[role="dialog"] button')).find((b) => b.textContent === 'Ops');
    await m.click(ops ?? null);
    expect(onChange).toHaveBeenCalledWith('ws-2');
    expect(m.host.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('closes on Escape, focus back on its button', async () => {
    const { trigger, m } = await open();
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(trigger.getAttribute('aria-controls')).toBe(m.host.querySelector('[role="dialog"]')?.id);
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
    expect(m.host.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('closes when the focus leaves it', async () => {
    const { m } = await open();
    const elsewhere = document.createElement('button');
    document.body.append(elsewhere);
    await act(async () => elsewhere.focus());
    expect(m.host.querySelector('[role="dialog"]')).toBeNull();
    elsewhere.remove();
  });
});
