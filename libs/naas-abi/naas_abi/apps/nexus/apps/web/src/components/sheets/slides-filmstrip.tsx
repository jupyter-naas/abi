'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { resolveSheetsPreviewAssets } from './sheets-assets';
import { type SlideOutlineItem } from './sheets-outline';
import { SheetsSlideThumb } from './sheets-cover-thumb';

export function SheetsFilmstrip({
  html,
  workspaceId,
  slug,
  sheets,
  selectedIndex,
  disabled,
  onSelect,
  onReorder,
}: {
  html: string;
  workspaceId: string;
  slug: string;
  sheets: SlideOutlineItem[];
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
    void resolveSheetsPreviewAssets(html, workspaceId, slug).then((resolved) => {
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
  }, [selectedIndex, sheets.length]);

  return (
    <div
      className="flex min-h-0 min-w-0 flex-1 flex-col"
      aria-label="Slide filmstrip"
      data-testid="sheets-filmstrip"
      data-orientation="vertical"
    >
      <ol
        ref={scrollerRef}
        className="flex min-h-0 flex-1 flex-col items-center gap-2 overflow-y-auto px-2 py-2"
      >
        {sheets.map((slide) => {
          const active = slide.index === selectedIndex;
          const label = slide.title || `Slide ${slide.index + 1}`;
          return (
            <li key={`${slide.index}-${slide.id || 'slide'}`} className="w-full max-w-[12rem]">
              <button
                ref={active ? selectedRef : undefined}
                type="button"
                title={label}
                aria-current={active ? 'true' : undefined}
                draggable={!disabled}
                onClick={() => onSelect(slide.index)}
                onDragStart={() => setDragging(slide.index)}
                onDragEnd={() => setDragging(null)}
                onDragOver={(event) => {
                  event.preventDefault();
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  if (dragging == null || dragging === slide.index) return;
                  onReorder(dragging, slide.index);
                  setDragging(null);
                }}
                className={cn(
                  'flex w-full flex-col items-center gap-1 rounded-sm text-left',
                  dragging === slide.index && 'opacity-50',
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
                  <SheetsSlideThumb html={thumbHtml} index={slide.index} title={label} />
                </span>
                <span
                  className={cn(
                    'text-[10px] tabular-nums leading-none',
                    active ? 'font-semibold text-workspace-accent' : 'text-muted-foreground',
                  )}
                >
                  {slide.index + 1}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
