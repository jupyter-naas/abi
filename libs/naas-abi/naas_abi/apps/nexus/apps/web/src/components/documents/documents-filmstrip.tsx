'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { resolveDocumentsPreviewAssets } from './documents-assets';
import { type SectionOutlineItem } from './documents-outline';
import { SectionsSectionThumb } from './documents-cover-thumb';

export function DocumentsOutline({
  html,
  workspaceId,
  slug,
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
  const [thumbHtml, setThumbHtml] = useState(html);
  const scrollerRef = useRef<HTMLOListElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let cancelled = false;
    setThumbHtml(html);
    if (!html || !workspaceId || !slug) return;
    void resolveDocumentsPreviewAssets(html, workspaceId, slug).then((resolved) => {
      if (!cancelled) setThumbHtml(resolved);
    });
    return () => {
      cancelled = true;
    };
  }, [html, workspaceId, slug]);

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
      aria-label="Section outline"
      data-testid="documents-outline"
      data-orientation="vertical"
    >
      <ol
        ref={scrollerRef}
        className="flex min-h-0 flex-1 flex-col items-center gap-2 overflow-y-auto px-2 py-2"
      >
        {sections.map((section) => {
          const active = section.index === selectedIndex;
          const label = section.title || `Section ${section.index + 1}`;
          return (
            <li key={`${section.index}-${section.id || 'section'}`} className="w-full max-w-[12rem]">
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
                  'flex w-full flex-col items-center gap-1 rounded-sm text-left',
                  dragging === section.index && 'opacity-50',
                )}
              >
                <span
                  className={cn(
                    'block aspect-video w-full overflow-hidden rounded-[2px] bg-muted/30',
                    active
                      ? 'ring-2 ring-workspace-accent ring-offset-1 ring-offset-card'
                      : 'ring-1 ring-border hover:ring-muted-foreground/50',
                  )}
                >
                  <SectionsSectionThumb html={thumbHtml} index={section.index} title={label} />
                </span>
                <span
                  className={cn(
                    'text-[10px] tabular-nums leading-none',
                    active ? 'font-semibold text-workspace-accent' : 'text-muted-foreground',
                  )}
                >
                  {section.index + 1}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
