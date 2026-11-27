// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, createElement, Fragment, useEffect, useState } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: () => undefined }), usePathname: () => '/settings/theme' }));

import { escapeLeavesSettings } from '@/components/settings/settings-shell-header';
import { Dialog } from './dialog';
import { ConfirmDialog, PromptDialog } from './dialogs';

let mounted: Mounted | null = null;

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

function press(key: string, init: KeyboardEventInit = {}, target: Element | null = document.activeElement) {
  const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init });
  (target ?? document.body).dispatchEvent(event);
  return event;
}

/** A settings page: its Escape handler is on the window first (the layout mounts before any dialog). */
function SettingsPage({ onBack, onClose }: { onBack: () => void; onClose: () => void }) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const leave = (event: KeyboardEvent) => {
      if (!escapeLeavesSettings(event)) return;
      event.preventDefault();
      onBack();
    };
    window.addEventListener('keydown', leave);
    setReady(true);
    return () => window.removeEventListener('keydown', leave);
  }, [onBack]);
  return ready
    ? createElement(Dialog, {
        title: 'Cancel run?',
        onClose,
        footer: createElement('button', { type: 'button' }, 'Keep running'),
      })
    : null;
}

describe('Dialog', () => {
  it('closes on Escape on a settings page instead of leaving Settings', async () => {
    const onBack = vi.fn();
    const onClose = vi.fn();
    mounted = await mount(SettingsPage, { onBack, onClose });
    // Focus is on a footer button, not a field: the case that used to leave Settings.
    expect(document.activeElement?.textContent).toBe('Keep running');
    await act(async () => void press('Escape'));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onBack).not.toHaveBeenCalled();
    expect(document.querySelector('[role="dialog"]')?.getAttribute('data-state')).toBe('open');
  });

  it('answers Escape in the topmost dialog only when two are stacked', async () => {
    const outer = vi.fn();
    const inner = vi.fn();
    mounted = await mount(
      () =>
        createElement(
          Fragment,
          null,
          createElement(Dialog, { title: 'Task', onClose: outer }, createElement('button', { type: 'button' }, 'Delete')),
          createElement(Dialog, { title: 'Delete the task?', onClose: inner }, createElement('button', { type: 'button' }, 'Cancel'))
        ),
      {}
    );
    await act(async () => void press('Escape'));
    expect(inner).toHaveBeenCalledTimes(1);
    expect(outer).not.toHaveBeenCalled();
  });

  it('brings focus back inside when something outside took it', async () => {
    const outside = document.createElement('button');
    document.body.append(outside);
    mounted = await mount(
      () => createElement(Dialog, { title: 'Rename', onClose: () => undefined }, createElement('input', { 'aria-label': 'Name' })),
      {}
    );
    outside.focus();
    await act(async () => void press('Tab', {}, outside));
    expect(document.querySelector('[role="dialog"]')?.contains(document.activeElement)).toBe(true);
  });
});

describe('PromptDialog and ConfirmDialog', () => {
  it('name their field and submit once on ⌘/Ctrl+Enter', async () => {
    const onConfirm = vi.fn();
    mounted = await mount(
      () =>
        createElement(PromptDialog, {
          open: true,
          title: 'Sheet name',
          defaultValue: 'Sheet 1',
          onConfirm,
          onCancel: () => undefined,
        }),
      {}
    );
    const input = document.querySelector('[role="dialog"] input') as HTMLInputElement;
    expect(document.querySelector(`label[for="${input.id}"]`)?.textContent).toBe('Sheet name');
    await act(async () => void press('Enter', { ctrlKey: true }, input));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('labels the type-to-confirm field and keeps the action off until it matches', async () => {
    const onConfirm = vi.fn();
    mounted = await mount(
      () =>
        createElement(ConfirmDialog, {
          open: true,
          title: 'Remove 3 individuals?',
          confirmText: '3',
          confirmLabel: 'Remove',
          onConfirm,
          onCancel: () => undefined,
        }),
      {}
    );
    const input = document.querySelector('[role="dialog"] input') as HTMLInputElement;
    expect(document.querySelector(`label[for="${input.id}"]`)?.textContent).toContain('to confirm');
    await act(async () => void press('Enter', { metaKey: true }, input));
    expect(onConfirm).not.toHaveBeenCalled();
    await mounted.type(input, '3');
    await act(async () => void press('Enter', { metaKey: true }, input));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
