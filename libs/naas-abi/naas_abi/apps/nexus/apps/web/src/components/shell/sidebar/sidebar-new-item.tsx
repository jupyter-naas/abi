'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { ChevronDown, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import './sidebar-new-item.css';

/**
 * The create row a sidebar section puts above its list.
 *
 * New Chat is the reference; New Slides is the same control with a template
 * picker hanging off it. Both render from `sidebar-new-item.css`, so the size,
 * spacing, weight and hover state are the same rule rather than two that
 * happen to agree today.
 *
 * The menu is controlled by the caller, which keeps this component pure enough
 * to assert on in both states and matches the `MenuDropdown` in the Slides
 * menu bar.
 */

export type SidebarNewItemMenuOption = {
  id: string;
  label: string;
  description?: string;
  /** Namespace shown ahead of the label, as ``<prefix>/``. Omit to hide it. */
  prefix?: string;
  /** Small colour chip, e.g. a template accent. */
  swatch?: string;
  disabled?: boolean;
  onSelect: () => void;
};

export function SidebarNewItem({
  label,
  icon,
  onClick,
  disabled,
  active,
  mobilePanel,
  title,
  menuLabel,
  menuOptions,
  menuOpen,
  onMenuOpenChange,
  menuEmptyLabel = 'No templates loaded',
}: {
  label: string;
  icon?: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  mobilePanel?: boolean;
  title?: string;
  /** Accessible name for the caret; omit to render the plain button. */
  menuLabel?: string;
  menuOptions?: SidebarNewItemMenuOption[];
  menuOpen?: boolean;
  onMenuOpenChange?: (open: boolean) => void;
  menuEmptyLabel?: string;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const hasMenu = Boolean(menuLabel && onMenuOpenChange);

  useEffect(() => {
    if (!menuOpen || !onMenuOpenChange) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) onMenuOpenChange(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onMenuOpenChange(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [menuOpen, onMenuOpenChange]);

  return (
    <div ref={rootRef} className="sidebar-new-item-group">
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        title={title}
        className={cn(
          'sidebar-new-item',
          active && 'is-active',
          mobilePanel && 'is-mobile-panel',
        )}
      >
        {icon ?? <Plus size={mobilePanel ? 14 : 12} />}
        <span className="truncate">{label}</span>
      </button>

      {hasMenu ? (
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded={Boolean(menuOpen)}
          aria-label={menuLabel}
          title={menuLabel}
          disabled={disabled}
          onClick={() => onMenuOpenChange?.(!menuOpen)}
          className={cn(
            'sidebar-new-item-caret',
            menuOpen && 'is-open',
            mobilePanel && 'is-mobile-panel',
          )}
        >
          <ChevronDown size={mobilePanel ? 14 : 12} />
        </button>
      ) : null}

      {hasMenu && menuOpen ? (
        <div
          role="menu"
          aria-label={menuLabel}
          className="absolute left-0 top-full z-[300] mt-1 min-w-[13rem] rounded-md border border-border bg-card py-1 shadow-lg"
        >
          {(menuOptions ?? []).length === 0 ? (
            <p className="px-3 py-1.5 text-xs text-muted-foreground">{menuEmptyLabel}</p>
          ) : (
            (menuOptions ?? []).map((option) => (
              <button
                key={option.id}
                type="button"
                role="menuitem"
                disabled={option.disabled}
                onClick={() => {
                  if (option.disabled) return;
                  option.onSelect();
                  onMenuOpenChange?.(false);
                }}
                className={cn(
                  'flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors',
                  option.disabled
                    ? 'cursor-not-allowed text-muted-foreground/50'
                    : 'hover:bg-muted',
                )}
              >
                {option.swatch ? (
                  <span
                    aria-hidden
                    className="h-2.5 w-2.5 flex-shrink-0 rounded-sm border border-border/70"
                    style={{ background: option.swatch }}
                  />
                ) : null}
                {option.prefix ? (
                  <span className="flex-shrink-0 font-mono text-[10px] text-muted-foreground">
                    {option.prefix}/
                  </span>
                ) : null}
                <span className="min-w-0 flex-1 truncate">{option.label}</span>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
