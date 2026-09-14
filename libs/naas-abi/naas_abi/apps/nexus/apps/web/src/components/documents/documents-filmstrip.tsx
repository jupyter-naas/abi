'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { type SectionOutlineItem } from './documents-outline';

export function DocumentsOutline({
  html: _html,
  workspaceId: _workspaceId,
  slug: _slug,
  sections,
  selectedIndex,
  disabled,
  onSelect,
  onReorder,
}: {
  html: string;
  workspaceId: string;
  slug: string;
  sections: SectionOutlineItem[];
  selectedIndex: number;
  disabled?: boolean;
  onSelect: (index: number) => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
}) {
  const [dragging, setDragging] = useState<number | null>(null);
  const scrollerRef = useRef<HTMLOListElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const scroller = scrollerRef.current;
    const selected = selectedRef.current;
    if (!scroller || !selected) return;
    const reveal = () => {
      if (scroller.clientHeight < selected.offsetHeight) return;
      selected.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      });
    };
    reveal();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => reveal());
    ro.observe(scroller);
    return () => ro.disconnect();
  }, [selectedIndex, sections.length]);

  return (
    <div
      className="flex min-h-0 min-w-0 flex-1 flex-col"
      aria-label="Document outline"
      data-testid="documents-outline"
      data-orientation="vertical"
    >
      <ol
        ref={scrollerRef}
        className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-2"
      >
        {sections.map((section) => {
          const active = section.index === selectedIndex;
          const label = section.title || `Heading ${section.index + 1}`;
          return (
            <li key={`${section.index}-${section.id || 'section'}`} className="w-full">
              <button
                ref={active ? selectedRef : undefined}
                type="button"
                title={label}
                aria-current={active ? 'true' : undefined}
                draggable={!disabled}
                onClick={() => onSelect(section.index)}
                onDragStart={() => setDragging(section.index)}
                onDragEnd={() => setDragging(null)}
                onDragOver={(event) => {
                  event.preventDefault();
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  if (dragging == null || dragging === section.index) return;
                  onReorder(dragging, section.index);
                  setDragging(null);
                }}
                className={cn(
                  'flex w-full items-start gap-2 rounded-sm px-2 py-1.5 text-left',
                  dragging === section.index && 'opacity-50',
                  active
                    ? 'bg-workspace-accent/10 text-workspace-accent'
                    : 'text-foreground hover:bg-muted/70',
                )}
              >
                <span
                  className={cn(
                    'w-4 shrink-0 pt-0.5 text-[10px] tabular-nums leading-none',
                    active ? 'font-semibold' : 'text-muted-foreground',
                  )}
                >
                  {section.index + 1}
                </span>
                <span className="min-w-0 flex-1 truncate text-xs leading-snug">{label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
