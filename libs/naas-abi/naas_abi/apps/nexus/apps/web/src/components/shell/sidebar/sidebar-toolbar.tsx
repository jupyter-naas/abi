'use client';

import React from 'react';
import { cn } from '@/lib/utils';

/**
 * Horizontal container for a section's quick-action icon buttons.
 * Standardises spacing/padding across every sidebar section.
 */
export function SidebarToolbar({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn('flex items-center gap-1 px-1 pb-1', className)}>
      {children}
    </div>
  );
}

/**
 * A single quick-action icon button used in sidebar section toolbars.
 * Matches the Knowledge Graph section styling: 28px square, rounded-md,
 * muted by default with a workspace-accent hover.
 */
export function SidebarToolbarButton({
  icon,
  label,
  onClick,
  disabled = false,
  spinning = false,
  active = false,
  className,
}: {
  icon: React.ReactNode;
  /** Used for both the tooltip (`title`) and the accessible name (`aria-label`). */
  label: string;
  onClick: (event: React.MouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
  /** Spins the icon — typically wired to a loading flag on a Refresh action. */
  spinning?: boolean;
  /** Highlights the button with the accent color (e.g. for the active view). */
  active?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={(event) => onClick(event)}
      disabled={disabled}
      title={label}
      aria-label={label}
      className={cn(
        'flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-workspace-accent disabled:opacity-50',
        active && 'bg-workspace-accent-10 text-workspace-accent',
        className,
      )}
    >
      <span className={cn('flex items-center justify-center', spinning && 'animate-spin')}>
        {icon}
      </span>
    </button>
  );
}
