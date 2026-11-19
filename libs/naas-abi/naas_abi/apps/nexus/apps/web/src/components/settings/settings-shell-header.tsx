'use client';

import { useEffect } from 'react';
import { ArrowLeft, Settings, type LucideIcon } from 'lucide-react';

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
  title = 'Settings',
  detailTitle,
  icon: Icon = Settings,
  onBack,
  backAriaLabel,
}: {
  /** Settings, or the Console: the levels are the column's, not the header's. */
  title?: string;
  /** The page's title on a phone, where the column is a screen of its own. */
  detailTitle?: string | null;
  icon?: LucideIcon;
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
          <Icon size={16} className="org-settings-layout-header-icon" />
          <h1 className="org-settings-layout-header-title">{detailTitle ?? title}</h1>
        </div>
      </div>
    </header>
  );
}
