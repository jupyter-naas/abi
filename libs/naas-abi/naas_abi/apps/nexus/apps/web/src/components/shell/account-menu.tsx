'use client';

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { LogOut, Search, Settings, UserRound } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { useSettingsHref, useWarmAvatarSettingsLinks } from '@/hooks/use-avatar-settings-links';
import { ROLE_LABELS, type BuiltInRole } from '@/components/access/roles/role-change';
import { ACCOUNT_SETTINGS_PATH, UserAvatar } from './user-avatar';
import { toggleWorkspacesPanel } from './toggle-workspaces-panel';

/** A box we can place against: a DOMRect, or a plain rectangle in tests. */
export type MenuAnchor = { top: number; bottom: number; left: number; width: number };

export type PlacedMenu = {
  /** Upward when the control has room above it (the dock). Down when it sits in the top bar. */
  open: 'up' | 'down';
  left: number;
  width: number;
  top?: number;
  bottom?: number;
  maxHeight: number;
};

const GUTTER = 8;
/** Icon rail is 56px; the rows need this much to be readable, aligned to the rail. */
const READABLE_WIDTH = 256;
const WIDE_COLUMN = 200;
/** Room required above the control before the menu opens upward. */
const UP_ROOM = 180;

/**
 * The menu sits in the nav column, above the identity row, at that column's width.
 * An icon rail is narrower than the rows, so the menu keeps a readable width on the
 * rail's left edge instead of opening a side sheet. A control in the phone's top bar
 * has no room above it, so the same menu opens just under that control.
 */
export function placeAccountMenu(
  anchor: MenuAnchor,
  column: MenuAnchor,
  viewport: { width: number; height: number },
): PlacedMenu {
  const cap = Math.max(0, viewport.width - GUTTER * 2);
  const width = Math.min(cap, column.width >= WIDE_COLUMN ? column.width : READABLE_WIDTH);
  let left = column.left;
  if (left + width > viewport.width - GUTTER) {
    left = Math.max(GUTTER, viewport.width - width - GUTTER);
  }
  const spaceAbove = anchor.top - GUTTER;
  if (spaceAbove >= UP_ROOM) {
    return { open: 'up', left, width, bottom: viewport.height - anchor.top, maxHeight: spaceAbove };
  }
  const top = anchor.bottom + GUTTER;
  return { open: 'down', left, width, top, maxHeight: Math.max(0, viewport.height - top - GUTTER) };
}

function memberRoleLabel(role: string | undefined): string | null {
  if (!role || !(role in ROLE_LABELS)) return null;
  return ROLE_LABELS[role as BuiltInRole];
}

/** "JOE · Admin" — the workspace name and the label the members page already uses. */
export function workspaceRoleLine(name: string, role: string | undefined): string {
  const label = memberRoleLabel(role);
  return label ? `${name} · ${label}` : name;
}

function triggerLabel(name: string): string {
  return name === 'User' ? 'Account menu' : `${name}, account menu`;
}

export function AccountMenu({
  labeled = false,
  placement = 'dock',
}: {
  labeled?: boolean;
  placement?: 'dock' | 'phone';
}) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [box, setBox] = useState<PlacedMenu | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const settingsHref = useSettingsHref();
  useWarmAvatarSettingsLinks();

  const displayUser = mounted ? user : null;
  const name = displayUser?.name || 'User';
  const current = mounted ? workspaces.find((w) => w.id === currentWorkspaceId) ?? null : null;
  const scopeLine = current ? workspaceRoleLine(current.name, current.currentUserRole) : '';

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const place = () => {
      const btn = btnRef.current;
      if (!btn) return;
      const anchor = btn.getBoundingClientRect();
      const column = (btn.closest('aside') ?? btn).getBoundingClientRect();
      setBox(placeAccountMenu(anchor, column, { width: window.innerWidth, height: window.innerHeight }));
    };
    place();
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      setOpen(false);
      btnRef.current?.focus();
    };
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node;
      if (btnRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPointer);
    window.addEventListener('resize', place);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointer);
      window.removeEventListener('resize', place);
    };
  }, [open]);

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label={triggerLabel(name)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={placement === 'dock' && !labeled ? name : undefined}
        className={cn(
          'flex items-center outline-none focus-visible:ring-0',
          placement === 'phone'
            ? 'h-8 w-8 flex-shrink-0 justify-center overflow-hidden rounded-full'
            : cn(
                'rounded-lg hover:bg-workspace-accent-10',
                open && 'bg-workspace-accent-10',
                labeled ? 'w-full gap-3 px-3 py-2' : 'h-10 w-10 justify-center',
              ),
        )}
      >
        <UserAvatar user={displayUser} className="h-8 w-8 flex-shrink-0" alt="" />
        {placement === 'dock' && labeled && (
          <span className="min-w-0 flex-1 text-left">
            <span className="block truncate text-sm font-medium text-foreground">{name}</span>
            {current && (
              <span className="block truncate text-xs text-muted-foreground">{current.name}</span>
            )}
          </span>
        )}
      </button>

      {open && mounted && box && createPortal(
        <div
          ref={menuRef}
          role="menu"
          aria-label="Account"
          data-open={box.open}
          data-org-branded="true"
          className={cn(
            'fixed z-[10000] overflow-y-auto border border-border/60 bg-card p-1 text-foreground shadow-lg',
            box.open === 'up' ? 'origin-bottom-left' : 'origin-top-left',
          )}
          style={{
            left: box.left,
            width: box.width,
            maxHeight: box.maxHeight,
            ...(box.open === 'up' ? { bottom: box.bottom } : { top: box.top }),
          }}
        >
          <div data-account-row="identity" className="px-3 py-2">
            <p data-account-name className="truncate text-sm font-medium" title={name}>{name}</p>
            {displayUser?.email && (
              <p data-account-email className="truncate text-xs text-muted-foreground" title={displayUser.email}>
                {displayUser.email}
              </p>
            )}
          </div>

          <div data-account-row="workspace" className="border-t border-border/50 px-3 py-2 text-xs text-muted-foreground">
            {scopeLine}
          </div>

          <button
            type="button"
            role="menuitem"
            data-account-row="find"
            className="flex w-full items-center gap-2 border-t border-border/50 px-3 py-2 text-left text-sm hover:bg-muted"
            onClick={() => {
              setOpen(false);
              toggleWorkspacesPanel();
            }}
          >
            <Search size={14} className="shrink-0 text-muted-foreground" />
            Find workspace
          </button>

          <Link
            href={ACCOUNT_SETTINGS_PATH}
            role="menuitem"
            data-account-row="account"
            className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted"
            onClick={() => setOpen(false)}
          >
            <UserRound size={14} className="shrink-0 text-muted-foreground" />
            Account
          </Link>

          <Link
            href={settingsHref}
            role="menuitem"
            data-account-row="settings"
            className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted"
            onClick={() => setOpen(false)}
          >
            <Settings size={14} className="shrink-0 text-muted-foreground" />
            Settings
          </Link>

          <button
            type="button"
            role="menuitem"
            data-account-row="logout"
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-destructive/10 hover:text-destructive"
            onClick={() => {
              setOpen(false);
              logout();
              router.push('/auth/login');
            }}
          >
            <LogOut size={14} className="shrink-0" />
            Log out
          </button>
        </div>,
        document.body,
      )}
    </>
  );
}
