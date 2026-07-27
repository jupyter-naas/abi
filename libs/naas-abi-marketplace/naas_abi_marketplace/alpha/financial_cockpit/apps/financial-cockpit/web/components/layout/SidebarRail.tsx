'use client';

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import Link from 'next/link';

import type { PageId, UserConfig } from '@/lib/types';
import type { NavEntry } from '@/lib/navModel';
import { ADMIN_SECTION_ID, entryKey } from '@/lib/navModel';
import { Logo } from '@/components/brand/Logo';
import { Button } from '@/components/ui/Button';
import {
  AdministrationIcon,
  ComptabiliteIcon,
  GenericPageIcon,
  OperationsIcon,
  PerformanceIcon,
  PilotageIcon,
  ReferentielsIcon,
  TreasuryIcon,
} from '@/components/layout/SidebarGroupIcons';

type IconComponent = React.ComponentType<{ className?: string }>;

const GROUP_ICONS: Record<string, IconComponent> = {
  performance: PerformanceIcon,
  pilotage: PilotageIcon,
  treasury: TreasuryIcon,
  operations: OperationsIcon,
  comptabilite: ComptabiliteIcon,
  referentiels: ReferentielsIcon,
  administration: AdministrationIcon,
};

/** One-line description shown under the title in the rail hover card. */
const SECTION_DESCRIPTIONS: Record<string, string> = {
  performance: 'Compte de résultat et analyse de la performance',
  pilotage: 'Budget et suivi du pilotage',
  treasury: 'Prévisions et positions de trésorerie',
  operations: 'Impayés clients et dettes fournisseurs',
  comptabilite: 'Écritures d’ajustement comptables',
  referentiels: 'Clients, fournisseurs et catégories',
  administration: 'Périmètres, utilisateurs, analytiques et thèmes',
};

type HoverCard = { title: string; description: string; top: number; left: number };

type SidebarRailProps = {
  entries: NavEntry[];
  pageLabels: Record<string, string>;
  currentPageId: PageId | null;
  adminActive: boolean;
  /** Panel entry currently open (section id, 'administration', or null). */
  activeKey: string | null;
  hrefFor: (pageId: PageId) => string;
  /** Open the secondary panel for a group / administration entry. */
  onSelectSection: (key: string) => void;
  user: UserConfig;
  onLogout: () => void;
};

/**
 * Narrow icon rail — the primary column of the double sidebar. One icon per
 * top-level nav entry: groups and Administration open the secondary panel;
 * flat pages navigate directly. The brand at the top links back to the
 * perimeter gallery, and the user menu is pinned at the bottom.
 */
export function SidebarRail({
  entries,
  pageLabels,
  currentPageId,
  adminActive,
  activeKey,
  hrefFor,
  onSelectSection,
  user,
  onLogout,
}: SidebarRailProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
  const [mounted, setMounted] = useState(false);
  const [hover, setHover] = useState<HoverCard | null>(null);
  const userBtnRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false);
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [menuOpen]);

  function openMenu() {
    const rect = userBtnRef.current?.getBoundingClientRect();
    if (rect) {
      setMenuPos({ top: rect.top, left: rect.right + 8 });
    }
    setMenuOpen((open) => !open);
  }

  function showHover(
    event: React.SyntheticEvent<HTMLElement>,
    title: string,
    description: string,
  ) {
    const rect = event.currentTarget.getBoundingClientRect();
    setHover({
      title,
      description,
      top: rect.top + rect.height / 2,
      left: rect.right + 10,
    });
  }

  const hideHover = () => setHover(null);

  function renderEntry(entry: NavEntry) {
    const key = entryKey(entry);
    const hoverProps = (title: string, description: string) => ({
      onMouseEnter: (e: React.MouseEvent<HTMLElement>) => showHover(e, title, description),
      onMouseLeave: hideHover,
      onFocus: (e: React.FocusEvent<HTMLElement>) => showHover(e, title, description),
      onBlur: hideHover,
    });

    if (entry.kind === 'page') {
      const label = pageLabels[entry.pageId] ?? entry.pageId;
      const description = SECTION_DESCRIPTIONS[entry.pageId] ?? '';
      const active = currentPageId === entry.pageId;
      return (
        <Link
          key={key}
          href={hrefFor(entry.pageId)}
          aria-label={label}
          aria-current={active ? 'page' : undefined}
          className={`sidebar-rail-item${active ? ' active' : ''}`}
          {...hoverProps(label, description)}
        >
          <GenericPageIcon className="sidebar-rail-icon" />
        </Link>
      );
    }

    const isAdmin = entry.kind === 'administration';
    const label = isAdmin ? 'Administration' : entry.label;
    const description = SECTION_DESCRIPTIONS[key] ?? '';
    const Icon = isAdmin
      ? AdministrationIcon
      : (GROUP_ICONS[entry.id] ?? GenericPageIcon);
    const routeActive = isAdmin
      ? adminActive
      : currentPageId !== null && entry.childIds.includes(currentPageId);
    const panelOpen = activeKey === key;

    return (
      <button
        key={key}
        type="button"
        aria-label={label}
        aria-expanded={panelOpen}
        onClick={() => onSelectSection(key)}
        className={`sidebar-rail-item${routeActive ? ' active' : ''}${
          panelOpen ? ' panel-open' : ''
        }`}
        {...hoverProps(label, description)}
      >
        <Icon className="sidebar-rail-icon" />
      </button>
    );
  }

  return (
    <aside className="shell-chrome flex h-full w-16 shrink-0 flex-col items-center overflow-visible border-r border-[var(--border)]">
      <Link
        href="/"
        aria-label="Périmètres"
        className="flex h-[var(--topbar-height)] w-full items-center justify-center border-b border-[var(--border)] outline-none transition-colors hover:bg-[var(--accent)] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-secondary"
        onMouseEnter={(e) =>
          showHover(e, 'Périmètres', 'Revenir à la sélection des périmètres')
        }
        onMouseLeave={hideHover}
        onFocus={(e) => showHover(e, 'Périmètres', 'Revenir à la sélection des périmètres')}
        onBlur={hideHover}
      >
        <Logo size={30} variant="plain" className="pointer-events-none shrink-0" />
      </Link>

      <nav
        aria-label="Sections"
        className="flex min-h-0 flex-1 flex-col items-center gap-1 overflow-y-auto py-3"
      >
        {entries.filter((entry) => entry.kind !== 'administration').map(renderEntry)}
      </nav>

      <div className="flex shrink-0 flex-col items-center gap-1 py-3">
        {entries
          .filter((entry) => entryKey(entry) === ADMIN_SECTION_ID)
          .map(renderEntry)}

        <button
          ref={userBtnRef}
          type="button"
          onClick={openMenu}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label={user.name}
          title={user.name}
          className="flex h-9 w-9 items-center justify-center bg-[var(--primary)] text-xs font-semibold text-[var(--on-primary)] outline-none transition-colors hover:bg-[color-mix(in_srgb,#ffffff_18%,var(--primary))] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-secondary"
        >
          {user.name.trim().charAt(0).toUpperCase()}
        </button>
      </div>

      {menuOpen && mounted
        ? createPortal(
            <>
              <div
                className="fixed inset-0 z-[199]"
                onClick={() => setMenuOpen(false)}
                aria-hidden
              />
              <div
                role="menu"
                className="fixed z-[200] w-56 border border-[color-mix(in_srgb,var(--on-primary)_20%,var(--primary))] bg-[var(--primary)] p-2 text-[var(--on-primary)] shadow-lg"
                style={{
                  left: menuPos.left,
                  bottom: `calc(100vh - ${menuPos.top}px + 8px)`,
                }}
              >
                <div className="px-2 pb-2 pt-1 text-xs text-[color-mix(in_srgb,var(--on-primary)_70%,var(--primary))]">
                  Connecté en tant que
                  <div className="truncate text-sm font-medium text-[var(--on-primary)]">
                    {user.name}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  onPress={() => {
                    setMenuOpen(false);
                    onLogout();
                  }}
                  className="w-full justify-start !text-[var(--on-primary)] data-[hovered]:!bg-[color-mix(in_srgb,#ffffff_14%,var(--primary))]"
                >
                  Déconnexion
                </Button>
              </div>
            </>,
            document.body,
          )
        : null}

      {hover && mounted && !menuOpen
        ? createPortal(
            <div
              role="tooltip"
              className="pointer-events-none fixed z-[210] w-60 max-w-[16rem] -translate-y-1/2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2 shadow-lg"
              style={{ left: hover.left, top: hover.top }}
            >
              <p className="text-sm font-semibold text-[var(--text)]">{hover.title}</p>
              {hover.description ? (
                <p className="mt-0.5 text-xs leading-snug text-[var(--text-muted)]">
                  {hover.description}
                </p>
              ) : null}
            </div>,
            document.body,
          )
        : null}
    </aside>
  );
}
