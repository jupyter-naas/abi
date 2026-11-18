'use client';

import { useEffect } from 'react';
import { ArrowLeft, type LucideIcon } from 'lucide-react';
import { SettingsScopeSwitcher } from './settings-scope-switcher';

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
  scopeTitle,
  detailTitle,
  showScopeSwitcher,
  icon,
  onBack,
  backAriaLabel,
}: {
  /** Scope name in the list view (Platform Settings, org name, user name). */
  scopeTitle: string;
  /** Section title on mobile detail; replaces the switcher. */
  detailTitle?: string | null;
  showScopeSwitcher: boolean;
  icon?: LucideIcon;
  onBack: () => void;
  backAriaLabel: string;
}) {
  const ScopeIcon = icon;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!escapeLeavesSettings(event)) return;
      event.preventDefault();
      onBack();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onBack]);

  const title = detailTitle ?? scopeTitle;

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
        {showScopeSwitcher ? (
          <SettingsScopeSwitcher title={scopeTitle} icon={icon} />
        ) : (
          <div className="org-settings-layout-header-meta">
            {ScopeIcon ? <ScopeIcon size={16} className="org-settings-layout-header-icon" /> : null}
            <h1 className="org-settings-layout-header-title">{title}</h1>
          </div>
        )}
      </div>
    </header>
  );
}