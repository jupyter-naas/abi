'use client';

import type { GraphTableSizing } from './use-graph-table-sizing';
import './graph-table.css';

export function ColumnResizeHandle({ id, label, sizing }: {
  id: string;
  label: string;
  sizing: GraphTableSizing;
}) {
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={`Resize ${label} column`}
      aria-valuemin={sizing.minWidth(id)}
      aria-valuenow={Math.round(sizing.colWidths[id] ?? 160)}
      tabIndex={0}
      title="Drag to resize · Double-click to fit content"
      data-column-resize=""
      data-testid={`column-resize-${id}`}
      className={`graph-table-resize${sizing.activeResizeCol === id ? ' is-resizing' : ''}`}
      onPointerDown={(event) => sizing.startResize(event, id)}
      onClick={(event) => event.stopPropagation()}
      onDoubleClick={(event) => { event.stopPropagation(); sizing.autoFit(id); }}
      onDragStart={(event) => { event.preventDefault(); event.stopPropagation(); }}
      onKeyDown={(event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Enter'].includes(event.key)) return;
        event.preventDefault();
        event.stopPropagation();
        if (event.key === 'Enter') sizing.autoFit(id);
        else sizing.setWidth(id, (sizing.colWidths[id] ?? 160) +
          (event.key === 'ArrowRight' ? 1 : -1) * (event.shiftKey ? 40 : 10));
      }}
    />
  );
}
