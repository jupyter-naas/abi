'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { ArrowLeft, Settings } from 'lucide-react';
import type { SettingsTab } from './settings-levels';

// Open layers that take Esc for themselves: dialogs, menus, listboxes, popovers.
const OPEN_LAYER =
  '[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"], dialog[open], ' +
  '[role="menu"], [role="listbox"], [data-radix-popper-content-wrapper]';

const EDITABLE = 'input, textarea, select, [contenteditable]:not([contenteditable="false"])';

/**
 * Whether Esc leaves settings: not when something already handled it, when the
 * caller is typing in a field, or when a dialog, menu or popover is open.
 */
export function escapeLeavesSettings(event: KeyboardEvent, doc: Document = document): boolean {
  if (event.key !== 'Escape' || event.defaultPrevented) return false;
  const target = event.target;
  if (target instanceof Element && target.closest(EDITABLE)) return false;
  return !doc.querySelector(OPEN_LAYER);
}

export function SettingsShellHeader({
  detailTitle,
  tabs = [],
  onBack,
  backAriaLabel,
}: {
  /** The page's title on a phone, where the column is a screen of its own. */
  detailTitle?: string | null;
  /** The levels the caller opens (`useSettingsTabs`), under the title; none on a phone's page. */
  tabs?: SettingsTab[];
  onBack: () => void;
  backAriaLabel: string;
}) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!escapeLeavesSettings(event)) return;
      event.preventDefault();
      onBack();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onBack]);

  return (
    <>
      <header className="org-settings-layout-header">
        <div className="org-settings-layout-header-inner">
          <button
            type="button"
            onClick={onBack}
            className="org-settings-back-button"
            aria-label={backAriaLabel}
          >
            <ArrowLeft size={20} />
          </button>
          <div className="org-settings-layout-header-meta">
            <Settings size={16} className="org-settings-layout-header-icon" />
            <h1 className="org-settings-layout-header-title">{detailTitle ?? 'Settings'}</h1>
          </div>
        </div>
      </header>
      {tabs.length > 0 && (
        <nav className="settings-tabs" aria-label="Settings levels">
          {tabs.map((tab) => (
            <Link
              key={tab.id}
              href={tab.href}
              title={tab.label}
              aria-current={tab.active ? 'true' : undefined}
              className={tab.active ? 'settings-tab settings-tab-active' : 'settings-tab'}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
      )}
    </>
  );
}
