// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { FEATURE_KEYS, type FeatureKey } from '@/lib/feature-access';
import { mount, type Mounted } from '@/lib/testing/mount';
import { useWorkspaceStore } from '@/stores/workspace';
import { AppsMenuBar, type AppsMenuBarProps } from './apps-menu-bar';

function memberHolding(features: FeatureKey[]) {
  const featureFlags = Object.fromEntries(FEATURE_KEYS.map((feature) => [feature, features.includes(feature)]));
  useWorkspaceStore.setState({
    currentWorkspaceId: 'ws-1',
    workspaces: [{ id: 'ws-1', name: 'Ops', currentUserRole: 'member', featureFlags }] as never,
  });
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

async function openFile(props: AppsMenuBarProps): Promise<string[]> {
  mounted = await mount(AppsMenuBar, props);
  const file = mounted.host.querySelector('[data-testid="apps-menu-file"]');
  if (!file) return [];
  await mounted.click(file);
  const menu = mounted.host.querySelector('[data-testid="apps-menu-file-dropdown"]');
  return [...(menu?.children ?? [])].map((row) =>
    row.getAttribute('role') === 'separator' ? '---' : (row.textContent ?? '').trim(),
  );
}

describe('AppsMenuBar', () => {
  it('has File → New App for a member holding the apps feature', async () => {
    memberHolding(['chat', 'files', 'apps']);
    expect(await openFile({ onNewApp: () => undefined })).toEqual(['New App']);
  });

  it('has no New App for a member without the apps feature, nor an empty File menu', async () => {
    memberHolding(['chat', 'files']);
    expect(await openFile({ onNewApp: () => undefined })).toEqual([]);
    expect(mounted?.host.querySelector('[data-testid="apps-menu-file"]')).toBeNull();
    expect(mounted?.host.querySelector('[data-testid="apps-menuitem-new"]')).toBeNull();
  });

  it('keeps the open app\'s File extras without New App, with no leading separator', async () => {
    const fileExtras = [{ id: 'all-apps', label: 'All apps', onSelect: () => undefined }];
    memberHolding(['chat', 'files']);
    expect(await openFile({ onNewApp: () => undefined, fileExtras })).toEqual(['All apps']);
    await mounted?.unmount();
    memberHolding(['apps']);
    expect(await openFile({ onNewApp: () => undefined, fileExtras })).toEqual(['New App', '---', 'All apps']);
  });
});
