'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { ChevronRight, type LucideIcon } from 'lucide-react';
import { applyBrandColorVariables, brandColorVariables } from '@/lib/color';
import './settings-shell.css';

export type SettingsBrand = { primary: string | null; accent: string | null };

/**
 * Root of the settings shells (Organization Settings, Platform Settings).
 *
 * Colours: the workspace shell writes the last workspace's theme onto <html>, so
 * each settings area sets its own. With a `brand` (an organization's colours)
 * every colour token takes them; without one, the platform defaults apply.
 * They go on this root (first paint) and on <html> while it is mounted, so
 * dropdown menus, popovers and dialogs rendered in portals match; leaving the
 * settings restores the previous values.
 */
export function SettingsLayoutRoot({
  brand,
  borderRadius,
  className,
  children,
}: {
  /** Organization colours; omit for the platform defaults. */
  brand?: SettingsBrand | null;
  /** Corner radius in px (organization branding). */
  borderRadius?: string;
  className?: string;
  children: React.ReactNode;
}) {
  const brandPrimary = brand?.primary ?? null;
  const brandAccent = brand?.accent ?? null;
  const brandVariables = brand ? brandColorVariables(brandPrimary, brandAccent) : {};
  const usesPlatformColors = Object.keys(brandVariables).length === 0;

  useEffect(
    () =>
      applyBrandColorVariables(
        document.documentElement.style,
        brandColorVariables(brandPrimary, brandAccent)
      ),
    [brandPrimary, brandAccent]
  );
  const style = {
    ...(borderRadius !== undefined ? { '--org-border-radius': `${borderRadius}px` } : {}),
    ...brandVariables,
  } as React.CSSProperties;
  return (
    <div
      className={[
        'org-settings-layout-root',
        usesPlatformColors && 'settings-layout-root-platform-colors',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      data-org-settings-root=""
      data-org-branded="true"
      style={style}
    >
      {children}
    </div>
  );
}

/** One entry of the settings nav; the chevron marks the mobile list. */
export function SettingsNavItem({
  href,
  label,
  icon: Icon,
  active,
  chevron = false,
}: {
  href: string;
  label: string;
  icon: LucideIcon;
  active: boolean;
  chevron?: boolean;
}) {
  return (
    <li>
      <Link
        href={href}
        className={active ? 'org-settings-nav-item org-settings-nav-item-active' : 'org-settings-nav-item'}
        aria-current={active ? 'page' : undefined}
      >
        <Icon size={18} />
        <span className="org-settings-nav-item-label">{label}</span>
        {chevron && <ChevronRight size={18} className="org-settings-nav-item-chevron" />}
      </Link>
    </li>
  );
}
