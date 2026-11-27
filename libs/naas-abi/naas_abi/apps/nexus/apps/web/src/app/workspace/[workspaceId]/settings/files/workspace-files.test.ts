// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { FileRow, OfferApi, OfferState } from '@/lib/access-model/workspace-offer';
import type { FeatureAccessApi } from '../features/feature-access-api';
import type { FeatureAccessState, FeatureRow } from '../features/feature-access-model';
import { WorkspaceFiles } from './workspace-files';

const fileRow = (over: Partial<FileRow> & Pick<FileRow, 'key' | 'label'>): FileRow => ({
  mode: 'off',
  modes: ['off', 'read', 'write'],
  choices: ['off', 'read', 'write'],
  editable: true,
  reason: null,
  ...over,
});

const offer = (files: FileRow[], viewers: 'read' | 'none' = 'read'): OfferState =>
  ({
    workspace_id: 'ws1',
    files,
    my_files: { members: 'write', viewers },
  }) as unknown as OfferState;

const featureRow = (over: Partial<FeatureRow> = {}): FeatureRow => ({
  key: 'files',
  label: 'Files',
  choice: 'everyone',
  principals: [],
  policy: null,
  hand_edited: false,
  offered: true,
  held: true,
  editable: true,
  reason: null,
  also: [],
  ...over,
});

const features = (rows: FeatureRow[], errors?: Record<string, string>): FeatureAccessState => ({
  workspace_id: 'ws1',
  scope: 'abi:nexus:organization/o/nexus:workspace/ws1',
  access_policy: null,
  members_group: null,
  can: { create: true, attach: true, detach: true, widen: true },
  features: rows,
  ...(errors ? { errors } : {}),
});

const FILES = [
  fileRow({ key: 'org_files', label: 'Organization Files', mode: 'read' }),
  fileRow({ key: 'platform_files', label: 'Platform Files' }),
  fileRow({ key: 'system_files', label: 'System Files', modes: ['off', 'read'], choices: ['off'], editable: true }),
];

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function render(offerApi: Partial<OfferApi>, featureApi: Partial<FeatureAccessApi>) {
  mounted = await mount(WorkspaceFiles, {
    workspaceId: 'ws1',
    offerApi: offerApi as OfferApi,
    featureApi: featureApi as FeatureAccessApi,
  });
  await mounted.flush();
  return mounted;
}

const choice = (m: Mounted, files: string, value: string) =>
  m.host.querySelector(`[data-files="${files}"] [data-choice="${value}"]`) as HTMLButtonElement | null;
const saveButton = (m: Mounted) => m.host.querySelector('[data-action="save"]') as HTMLButtonElement;
const bar = (m: Mounted) => m.host.querySelector('.org-settings-general-draft');

describe('WorkspaceFiles', () => {
  it('shows every kind of files in one place: Workspace, Organization, Platform, System and My Files', async () => {
    const m = await render(
      { read: vi.fn().mockResolvedValue(offer(FILES)) },
      { read: vi.fn().mockResolvedValue(features([featureRow()])) },
    );
    expect([...m.host.querySelectorAll('[data-files]')].map((row) => row.getAttribute('data-files'))).toEqual([
      'workspace',
      'org_files',
      'platform_files',
      'system_files',
      'my_files',
    ]);
    expect(choice(m, 'workspace', 'everyone')?.getAttribute('aria-checked')).toBe('true');
    expect(choice(m, 'org_files', 'read')?.getAttribute('aria-checked')).toBe('true');
    // System Files has no write mode, and a mode the caller may not give is disabled.
    expect(choice(m, 'system_files', 'write')).toBeNull();
    expect(choice(m, 'system_files', 'read')?.disabled).toBe(true);
    expect(m.host.textContent).toContain('Viewers read theirs');
    // The header of the pages under Features: its title and one total.
    expect(m.host.querySelector('h2')?.textContent).toBe('Files');
    expect(m.host.textContent).toContain('5 kinds of files');
  });

  it('is a form: changes wait for Save, faded until something changes, with the unsaved bar', async () => {
    const saveFeatures = vi.fn().mockResolvedValue(features([featureRow({ choice: 'nobody' })]));
    const saveFiles = vi.fn().mockResolvedValue(
      offer([FILES[0], { ...FILES[1], mode: 'write' }, FILES[2]]),
    );
    const m = await render(
      { read: vi.fn().mockResolvedValue(offer(FILES)), saveFiles },
      { read: vi.fn().mockResolvedValue(features([featureRow()])), save: saveFeatures },
    );
    expect(saveButton(m).disabled).toBe(true);
    expect(saveButton(m).className).toContain('org-settings-primary-button');
    expect(bar(m)).toBeNull();

    await m.click(choice(m, 'workspace', 'nobody'));
    await m.click(choice(m, 'platform_files', 'write'));
    expect(choice(m, 'workspace', 'nobody')?.getAttribute('aria-checked')).toBe('true');
    expect(choice(m, 'platform_files', 'write')?.getAttribute('aria-checked')).toBe('true');
    expect(saveFeatures).not.toHaveBeenCalled();
    expect(bar(m)?.textContent).toContain('Unsaved changes.');
    expect(saveButton(m).disabled).toBe(false);

    await m.click(saveButton(m));
    await m.flush();
    expect(saveFeatures).toHaveBeenCalledWith('ws1', [{ feature: 'files', choice: 'nobody' }]);
    expect(saveFiles).toHaveBeenCalledWith('ws1', { platform_files: 'write' });
    expect(choice(m, 'platform_files', 'write')?.getAttribute('aria-checked')).toBe('true');
    expect(bar(m)).toBeNull();
    expect(saveButton(m).disabled).toBe(true);
  });

  it('discards the changes, back to what the workspace holds', async () => {
    const m = await render(
      { read: vi.fn().mockResolvedValue(offer(FILES)) },
      { read: vi.fn().mockResolvedValue(features([featureRow()])) },
    );
    await m.click(choice(m, 'org_files', 'off'));
    expect(choice(m, 'org_files', 'off')?.getAttribute('aria-checked')).toBe('true');
    await m.click(m.host.querySelector('.org-settings-general-draft-discard'));
    expect(choice(m, 'org_files', 'read')?.getAttribute('aria-checked')).toBe('true');
    expect(bar(m)).toBeNull();
  });

  it('says why a change was refused, and keeps what IAM did not let the caller change read-only', async () => {
    const saveFeatures = vi
      .fn()
      .mockResolvedValue(features([featureRow()], { files: 'IAM does not let you give Files here.' }));
    const locked = fileRow({ key: 'platform_files', label: 'Platform Files', editable: false, reason: 'Only a platform admin widens it.' });
    const m = await render(
      { read: vi.fn().mockResolvedValue(offer([locked])) },
      { read: vi.fn().mockResolvedValue(features([featureRow()])), save: saveFeatures },
    );
    expect(choice(m, 'platform_files', 'read')?.disabled).toBe(true);
    expect(m.host.textContent).toContain('Only a platform admin widens it.');
    await m.click(choice(m, 'workspace', 'nobody'));
    await m.click(saveButton(m));
    await m.flush();
    expect(m.host.textContent).toContain('IAM does not let you give Files here.');
    // The change refused stays, unsaved, beside why.
    expect(choice(m, 'workspace', 'nobody')?.getAttribute('aria-checked')).toBe('true');
    expect(bar(m)).not.toBeNull();
  });
});
