'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { type SheetTabItem } from './sheets-outline';
import { SheetsTabThumb } from './sheets-cover-thumb';

export function SheetsTabStrip({
  html,
  tabs,
  selectedIndex,
  disabled,
  onSelect,
  onReorder,
}: {
  html: string;
  workspaceId?: string;
  slug?: string;
  tabs: SheetTabItem[];
  selectedIndex: number;
  disabled?: boolean;
  onSelect: (index: number) => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
}) {
  const [dragging, setDragging] = useState<number | null>(null);
  const thumbHtml = html;

  return (
    <nav
      className="flex flex-col gap-2 overflow-y-auto px-2 py-3"
      aria-label="Sheet tabs"
      data-testid="sheets-tab-strip"
    >
      <ul className="flex flex-col gap-2">
        {tabs.map((tab) => {
          const active = tab.index === selectedIndex;
          const label = tab.title || `Sheet ${tab.index + 1}`;
          return (
            <li key={`${tab.index}-${tab.id || 'tab'}`} className="w-full max-w-[12rem]">
              <button
                type="button"
                draggable={!disabled}
                disabled={disabled}
                aria-current={active ? 'true' : undefined}
                aria-label={`${label}, tab ${tab.index + 1} of ${tabs.length}`}
                onClick={() => onSelect(tab.index)}
                onDragStart={() => setDragging(tab.index)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => {
                  if (dragging == null || dragging === tab.index) return;
                  onReorder(dragging, tab.index);
                  setDragging(null);
                }}
                className={cn(
                  'flex w-full flex-col gap-1 rounded-md border p-1 text-left transition',
                  active ? 'border-workspace-accent bg-workspace-accent-10' : 'border-border bg-card',
                  disabled && 'opacity-50',
                  dragging === tab.index && 'opacity-50',
                )}
              >
                <SheetsTabThumb html={thumbHtml} index={tab.index} title={label} />
                <span className="truncate px-1 text-xs font-medium text-foreground">{label}</span>
                <span className="px-1 text-[10px] text-muted-foreground">Tab {tab.index + 1}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** @deprecated Use SheetsTabStrip */
export const SheetsFilmstrip = SheetsTabStrip;
