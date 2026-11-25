// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { PersonBack, PersonInfoSection } from './person-info';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('A person’s page, shown alone', () => {
  it('opens on Info: their name, email and id, read-only, with the page’s actions at its right', async () => {
    mounted = await mount(PersonInfoSection, {
      id: 'usr_ann',
      name: 'Ann Analyst',
      email: 'ann@example.com',
      actions: createElement('button', { type: 'button', 'data-action': 'view-as' }, 'View as'),
    });
    const input = (label: string) => document.querySelector(`[aria-label="${label}"]`) as HTMLInputElement;
    expect([input('Name').value, input('Email').value, input('ID').value]).toEqual(['Ann Analyst', 'ann@example.com', 'usr_ann']);
    for (const label of ['Name', 'Email', 'ID']) {
      expect(input(label).readOnly).toBe(true);
      expect(input(label).classList.contains('account-profile-field-input-readonly')).toBe(true);
    }
    expect(document.querySelector('h3')?.textContent).toBe('Info');
    expect(document.querySelector('[data-action="view-as"]')).not.toBeNull();
  });

  it('leads back to Users', async () => {
    const onClick = vi.fn();
    mounted = await mount(PersonBack, { onClick });
    await mounted.click(document.querySelector('[data-action="back"]'));
    expect(onClick).toHaveBeenCalled();
    expect(document.querySelector('[data-action="back"]')?.textContent).toContain('Users');
  });
});
