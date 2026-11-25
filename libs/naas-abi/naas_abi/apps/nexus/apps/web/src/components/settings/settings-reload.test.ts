// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, useEffect, useState } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));
vi.mock('next/navigation', () => ({ usePathname: () => '/workspace/ws-1/settings/agents' }));

import { useAuthStore, type User } from '@/stores/auth';
import { SettingsReloadButton, SettingsReloadProvider, useSettingsReloadGeneration } from './settings-reload';

const person = (id: string): User => ({ id, email: `${id}@example.invalid`, name: id, createdAt: new Date() });

let calls: string[] = [];
let mounts = 0;
let reads: (number | null)[] = [];
let mounted: Mounted | null = null;

beforeEach(() => {
  calls = [];
  mounts = 0;
  reads = [];
  useAuthStore.setState({ user: person('one'), csrfToken: 'csrf-one', isAuthenticated: true });
  vi.stubGlobal('fetch', vi.fn(async (input: string, init: RequestInit = {}) => {
    calls.push(`${(init.method ?? 'GET').toUpperCase()} ${new URL(input).pathname}`);
    return Response.json({});
  }));
});

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  vi.unstubAllGlobals();
});

/** A page with a field the user typed in; `generation` is null for a page that does not read again on Reload itself. */
function PageBody({ generation }: { generation: number | null }) {
  const [typed, setTyped] = useState('');
  useEffect(() => {
    mounts += 1;
  }, []);
  useEffect(() => {
    reads.push(generation);
  }, [generation]);
  return createElement(
    'div',
    null,
    createElement(SettingsReloadButton),
    createElement('input', { value: typed, onChange: (event: { target: { value: string } }) => setTyped(event.target.value) })
  );
}

function ReadsOnReload() {
  return createElement(PageBody, { generation: useSettingsReloadGeneration() });
}

function Plain() {
  return createElement(PageBody, { generation: null });
}

function Tree({ optIn, onReload }: { optIn: boolean; onReload: () => void }) {
  return createElement(SettingsReloadProvider, { onReload }, createElement(optIn ? ReadsOnReload : Plain));
}

/** Reload awaits the API (and a lazily loaded module): let it finish. */
async function settle() {
  for (let i = 0; i < 100 && reloadButton().disabled; i += 1) await mounted!.flush();
  expect(reloadButton().disabled).toBe(false);
}

const reloadButton = (): HTMLButtonElement => mounted!.host.querySelector<HTMLButtonElement>('button[aria-label="Reload"]')!;

describe('Settings Reload', () => {
  it('a page that reads again on Reload is not remounted: what the user typed stays', async () => {
    const onReload = vi.fn();
    mounted = await mount(Tree, { optIn: true, onReload });
    await mounted.type(mounted.host.querySelector('input'), 'unsaved');
    await mounted.click(reloadButton());
    await settle();

    expect(calls).toContain('POST /api/settings-cache/refresh');
    expect(onReload).toHaveBeenCalledTimes(1);
    expect(mounts).toBe(1);
    expect(mounted.host.querySelector('input')!.value).toBe('unsaved');
    // It read once on mount and once for the Reload.
    expect(reads).toEqual([0, 1]);
  });

  it('a page that does not say so is remounted, as before, so its reads run again', async () => {
    mounted = await mount(Tree, { optIn: false, onReload: () => undefined });
    await mounted.type(mounted.host.querySelector('input'), 'unsaved');
    await mounted.click(reloadButton());
    await settle();
    expect(mounts).toBe(2);
  });
});
