'use client';

import { useEffect, useRef, useState } from 'react';
import { Settings2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  GRAPH_PARAM_DEFS,
  GRAPH_VIEWS,
  GRAPH_VIEW_LABELS,
  PROCESS_COUNT_DEF,
  formatParamValue,
  type GraphParams,
  type GraphView,
} from './event-graph-params';

/**
 * The cockpit's `renderParamsPanel`: a gear popover with a 2D/3D tab strip and
 * every parameter it exposes, plus a reset.
 */
export function EventGraphParamsPanel({
  params,
  onChange,
  onSwitchView,
  onReset,
}: {
  params: GraphParams;
  onChange: (key: string, value: string | number | boolean) => void;
  onSwitchView: (view: GraphView) => void;
  onReset: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const renderRange = (
    key: string,
    def: { label: string; min: number; max: number; step: number; hint: string },
    value: number,
  ) => (
    <label key={key} className="block space-y-1">
      <span className="flex items-baseline justify-between text-[11px]">
        <span>{def.label}</span>
        <strong className="font-mono text-[10px]">{formatParamValue(key, value)}</strong>
      </span>
      <input
        type="range"
        min={def.min}
        max={def.max}
        step={def.step}
        value={value}
        onChange={(e) => onChange(key, Number(e.target.value))}
        className="h-1 w-full"
      />
      <em className="block text-[10px] not-italic leading-snug text-muted-foreground">{def.hint}</em>
    </label>
  );

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        title="Graph parameters"
        aria-label="Graph parameters"
        className={cn(
          'rounded border bg-background/80 p-1.5 text-muted-foreground hover:text-foreground',
          open && 'text-foreground',
        )}
      >
        <Settings2 size={13} />
      </button>

      {open && (
        <div className="absolute bottom-full right-0 z-30 mb-1 max-h-[70vh] w-80 overflow-y-auto rounded-lg border bg-background p-3 shadow-lg">
          <div role="tablist" className="flex gap-1 rounded-md border p-0.5">
            {GRAPH_VIEWS.map((view) => (
              <button
                key={view}
                type="button"
                role="tab"
                aria-selected={params.view === view}
                onClick={() => onSwitchView(view)}
                className={cn(
                  'flex-1 rounded px-2 py-1 text-[11px]',
                  params.view === view ? 'bg-muted font-medium text-foreground' : 'text-muted-foreground hover:bg-muted/60',
                )}
              >
                {GRAPH_VIEW_LABELS[view]}
              </button>
            ))}
          </div>

          <p className="mt-2 text-[10px] leading-snug text-muted-foreground">
            {params.view === '3d'
              ? 'Every cluster gets its own depth, projected in perspective. Drag the background to orbit; nodes cannot be dragged while orbiting.'
              : 'The flat view. Drag the background to pan, drag a node to move it.'}
          </p>

          <div className="mt-3 space-y-3">
            {renderRange('processCount', PROCESS_COUNT_DEF, params.processCount)}

            {Object.entries(GRAPH_PARAM_DEFS).map(([key, def]) => {
              if (def.type === 'select') {
                return (
                  <label key={key} className="block space-y-1">
                    <span className="text-[11px]">{def.label}</span>
                    <select
                      value={String(params[key])}
                      onChange={(e) => onChange(key, e.target.value)}
                      className="w-full rounded border bg-transparent px-1.5 py-1 text-[11px]"
                    >
                      {def.options.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <em className="block text-[10px] not-italic leading-snug text-muted-foreground">{def.hint}</em>
                  </label>
                );
              }
              if (def.type === 'toggle') {
                return (
                  <label key={key} className="block space-y-1">
                    <span className="flex items-center justify-between text-[11px]">
                      <span>{def.label}</span>
                      <input
                        type="checkbox"
                        checked={Boolean(params[key])}
                        onChange={(e) => onChange(key, e.target.checked)}
                        className="h-3 w-3"
                      />
                    </span>
                    <em className="block text-[10px] not-italic leading-snug text-muted-foreground">{def.hint}</em>
                  </label>
                );
              }
              return renderRange(key, def, Number(params[key]));
            })}
          </div>

          <button
            type="button"
            onClick={onReset}
            className="mt-3 w-full rounded border px-2 py-1 text-[11px] hover:bg-accent"
          >
            Reset to defaults
          </button>
        </div>
      )}
    </div>
  );
}
