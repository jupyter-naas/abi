'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

import {
  AdministrationIcon,
  AnalyticsIcon,
  PerimetersIcon,
  ThemeIcon,
  UsersIcon,
} from '@/components/layout/SidebarGroupIcons';

export type AdminSection = 'perimeters' | 'users' | 'analytics' | 'theme';

type IconComponent = React.ComponentType<{ className?: string }>;

type AdminNavItem = {
  id: AdminSection;
  href: string;
  label: string;
  icon: IconComponent;
};

export const ADMIN_NAV: readonly AdminNavItem[] = [
  { id: 'perimeters', href: '/admin', label: 'Périmètres', icon: PerimetersIcon },
  { id: 'users', href: '/admin/users', label: 'Utilisateurs', icon: UsersIcon },
  { id: 'analytics', href: '/admin/analytics', label: 'Analytiques', icon: AnalyticsIcon },
  { id: 'theme', href: '/admin/theme', label: 'Thèmes', icon: ThemeIcon },
];

function activeSectionFor(pathname: string): AdminSection | null {
  if (pathname === '/admin/theme' || pathname.startsWith('/admin/theme/')) return 'theme';
  if (pathname.startsWith('/admin/users')) return 'users';
  if (pathname.startsWith('/admin/analytics')) return 'analytics';
  if (pathname === '/admin' || pathname.startsWith('/admin/')) return 'perimeters';
  return null;
}

type AdminNavSectionProps = {
  /** Render inside PageNav (no extra wrapper/padding). */
  embedded?: boolean;
  /** Icon-only rail: labels and subpages are hidden. */
  collapsed?: boolean;
  /** Collapsed rail only: expand the sidebar when a nav icon is clicked. */
  onExpand?: () => void;
};

/**
 * Administration group in the unified sidebar. Rendered only for admins; it
 * mirrors the collapsible section pattern in PageNav but points at absolute
 * /admin routes. On entity pages it sits inline after Comptabilité; on admin
 * screens it is pinned above the footer.
 */
export function AdminNavSection({
  embedded = false,
  collapsed = false,
  onExpand,
}: AdminNavSectionProps) {
  const pathname = usePathname();
  const active = activeSectionFor(pathname);
  const [open, setOpen] = useState(active !== null);

  const content = collapsed ? (
    <Link
      href="/admin"
      onClick={onExpand}
      aria-label="Administration"
      className={`sidebar-nav-item sidebar-nav-section${active ? ' section-active' : ''}`}
    >
      <span className="contents" title="Administration">
        <AdministrationIcon className="sidebar-nav-icon" />
      </span>
      <span className="sidebar-nav-label">Administration</span>
    </Link>
  ) : (
    <div key="section-administration">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className={`sidebar-nav-item sidebar-nav-section${active ? ' section-active' : ''}`}
      >
        <AdministrationIcon className="sidebar-nav-icon" />
        <span className="sidebar-nav-label">Administration</span>
      </button>
      {open ? (
        <div className="sidebar-nav-sub">
          {ADMIN_NAV.map((item) => (
            <Link
              key={item.id}
              href={item.href}
              className={`sidebar-nav-subitem${item.id === active ? ' active' : ''}`}
              aria-current={item.id === active ? 'page' : undefined}
            >
              {item.label}
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <div
      className={`sidebar-nav shrink-0 ${collapsed ? 'sidebar-nav--collapsed px-2 pb-3' : 'px-3 pb-2'}`}
    >
      {content}
    </div>
  );
}
