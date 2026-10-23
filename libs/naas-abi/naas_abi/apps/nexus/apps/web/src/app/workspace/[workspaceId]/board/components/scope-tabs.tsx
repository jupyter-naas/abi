'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { isRecordDrag, readDraggedRecordId } from '@/components/database-view/views';
import { BOARD_SCOPES, SCOPE_LABELS, type BoardScope } from '@/lib/board';

/**
 * The board's tabs: three iterations, Inbox and Backlog. A card or row
 * dropped on a tab moves the task there.
 */
export function ScopeTabs({
  active,
  counts,
  onSelect,
  onDropTask,
}: {
  active: BoardScope;
  counts: Record<BoardScope, number>;
  onSelect: (scope: BoardScope) => void;
  onDropTask: (taskId: string, scope: BoardScope) => void;
}) {
  const [dropTarget, setDropTarget] = useState<BoardScope | null>(null);

  return (
    <div className="board-tabs" role="tablist">
      {BOARD_SCOPES.map((scope) => (
        <button
          key={scope}
          type="button"
          role="tab"
          aria-selected={scope === active}
          className={cn(
            'board-tab',
            scope === active && 'board-tab-active',
            dropTarget === scope && 'board-tab-drop',
          )}
          onClick={() => onSelect(scope)}
          onDragOver={(e) => {
            if (scope === active || !isRecordDrag(e)) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            if (dropTarget !== scope) setDropTarget(scope);
          }}
          onDragLeave={() => setDropTarget(null)}
          onDrop={(e) => {
            setDropTarget(null);
            const taskId = readDraggedRecordId(e);
            if (!taskId) return;
            e.preventDefault();
            onDropTask(taskId, scope);
          }}
        >
          {SCOPE_LABELS[scope]}
          <span className="board-tab-count">{counts[scope]}</span>
        </button>
      ))}
    </div>
  );
}
