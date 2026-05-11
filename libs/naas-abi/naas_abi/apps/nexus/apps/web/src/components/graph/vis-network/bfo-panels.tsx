'use client';

import { useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BFO_BUCKET_DEFS, BFO_COLORS } from '@/lib/bfo';

interface BFOBucketFiltersProps {
  activeBuckets: Set<string>;
  /**
   * Optional override of the buckets to display as "active" — useful when the
   * effective active set differs from user intent (e.g. all-disabled = all-on).
   */
  effectiveActiveBuckets?: Set<string>;
  onToggle: (bucketType: string) => void;
  nodesPerBucket?: Map<string, Array<{ id: string; label: string }>>;
  hiddenNodeIds?: Set<string>;
  onNodeToggle?: (nodeId: string) => void;
}

/**
 * Side panel listing the seven BFO buckets with active/inactive indicators,
 * per-bucket node counts, and per-node visibility toggles.
 *
 * Tooltip is portalled to `document.body` so it can extend past the panel.
 */
export function BFOBucketFilters({
  activeBuckets,
  effectiveActiveBuckets,
  onToggle,
  nodesPerBucket,
  hiddenNodeIds,
  onNodeToggle,
}: BFOBucketFiltersProps) {
  const [tooltip, setTooltip] = useState<{
    label: string;
    type: string;
    description: string;
    position: { top: number; left: number };
  } | null>(null);
  const [expandedBuckets, setExpandedBuckets] = useState<Set<string>>(new Set());

  const displayActive = effectiveActiveBuckets ?? activeBuckets;

  return (
    <div className="absolute top-4 right-4 z-10 max-h-[calc(100vh-8rem)] w-44 overflow-y-auto rounded-lg border bg-card/95 p-3 shadow-lg backdrop-blur-sm">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        BFO 7 Buckets
      </h4>
      <div className="flex flex-col gap-0.5">
        {BFO_BUCKET_DEFS.map((bucket) => {
          const colors = BFO_COLORS[bucket.type as keyof typeof BFO_COLORS];
          const anySelected = displayActive.size > 0;
          const isActive = displayActive.has(bucket.type);
          const bucketNodes = nodesPerBucket?.get(bucket.type) ?? [];
          const isExpanded = expandedBuckets.has(bucket.type);

          return (
            <div
              key={bucket.type}
              className={cn(
                'rounded-md transition-all',
                anySelected && !isActive ? 'opacity-30' : 'opacity-100',
              )}
            >
              <div className="flex items-center">
                <button
                  onClick={() => onToggle(bucket.type)}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    setTooltip({
                      label: bucket.label,
                      type: bucket.type,
                      description: bucket.description,
                      position: { top: rect.top, left: rect.left - 8 },
                    });
                  }}
                  onMouseLeave={() => setTooltip(null)}
                  className="flex flex-1 items-center gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-muted"
                >
                  <div
                    className="h-3 w-3 flex-shrink-0 rounded-full"
                    style={{ backgroundColor: colors.background }}
                  />
                  <strong className="flex-1">{bucket.label}</strong>
                  {bucketNodes.length > 0 && (
                    <span className="text-[10px] text-muted-foreground">{bucketNodes.length}</span>
                  )}
                </button>
                {bucketNodes.length > 0 && (
                  <button
                    onClick={() =>
                      setExpandedBuckets((prev) => {
                        const next = new Set(prev);
                        if (next.has(bucket.type)) next.delete(bucket.type);
                        else next.add(bucket.type);
                        return next;
                      })
                    }
                    className="px-1 py-1 text-muted-foreground hover:text-foreground"
                  >
                    <ChevronRight
                      size={10}
                      className={cn('transition-transform', isExpanded && 'rotate-90')}
                    />
                  </button>
                )}
              </div>
              {isExpanded && bucketNodes.length > 0 && (
                <div className="ml-3 mt-0.5 space-y-0.5 border-l border-border pl-2">
                  {bucketNodes.map((node) => {
                    const isHidden = hiddenNodeIds?.has(node.id) ?? false;
                    return (
                      <label
                        key={node.id}
                        className="flex cursor-pointer items-center gap-1.5 rounded px-1 py-0.5 hover:bg-muted"
                      >
                        <input
                          type="checkbox"
                          checked={!isHidden}
                          onChange={() => onNodeToggle?.(node.id)}
                          className="h-3 w-3 cursor-pointer"
                        />
                        <span className="max-w-[100px] truncate text-[11px]">{node.label}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {tooltip &&
        typeof document !== 'undefined' &&
        createPortal(
          <div
            className="fixed z-[100] whitespace-nowrap rounded-md border border-border bg-popover px-3 py-2 text-sm shadow-lg animate-in fade-in-0 zoom-in-95 duration-100"
            style={{
              top: tooltip.position.top,
              left: tooltip.position.left,
              transform: 'translateX(-100%)',
            }}
          >
            <p className="font-medium">
              {tooltip.label}{' '}
              <span className="font-normal text-muted-foreground">({tooltip.type})</span>
            </p>
            <p className="text-xs text-muted-foreground">{tooltip.description}</p>
          </div>,
          document.body,
        )}
    </div>
  );
}

/** Static legend for pages that don't need interactive bucket filtering. */
export function BFOLegend() {
  return (
    <div className="absolute top-4 right-4 z-10 rounded-lg border bg-card/95 p-3 shadow-lg backdrop-blur-sm">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        BFO 7 Buckets
      </h4>
      <div className="grid grid-cols-2 gap-2">
        {BFO_BUCKET_DEFS.map((bucket) => {
          const colors = BFO_COLORS[bucket.type as keyof typeof BFO_COLORS];
          return (
            <div key={bucket.type} className="flex items-center gap-2">
              <div
                className="h-3 w-3 rounded-full"
                style={{ backgroundColor: colors.background }}
              />
              <span className="text-xs">
                <strong>{bucket.label}</strong>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
