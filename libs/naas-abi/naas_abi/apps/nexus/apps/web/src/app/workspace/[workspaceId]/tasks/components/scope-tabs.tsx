'use client';

import { useState, type DragEvent } from 'react';
import { ChevronDown, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { isRecordDrag, readDraggedRecordId } from '@/components/database-view/drag';
import { Popover } from '@/components/database-view/primitives';
import { SCOPE_LABELS, type TasksScope } from '@/lib/tasks';

export interface LayoutOption<T extends string> {
  type: T;
  label: string;
  icon: LucideIcon;
}

/** A tab being dragged to a new place (distinct from a task card). */
const TAB_DRAG_MIME = 'application/x-nexus-tasks-tab';
const isTabDrag = (e: DragEvent<HTMLElement>) => Array.from(e.dataTransfer.types).includes(TAB_DRAG_MIME);

/** ``order`` with ``moved`` placed where ``target`` is. */
export function reorderScopes(order: TasksScope[], moved: TasksScope, target: TasksScope): TasksScope[] {
  if (moved === target) return order;
  const without = order.filter((s) => s !== moved);
  const index = without.indexOf(target);
  // Dropping on a tab to the right lands after it, to the left before it.
  const after = order.indexOf(moved) < order.indexOf(target);
  without.splice(after ? index + 1 : index, 0, moved);
  return without;
}

/**
 * The Tasks tabs: three iterations, Inbox and Backlog, each with the icon of
 * its layout (Board, Table, Gallery, Calendar) like Notion views. The active
 * tab's caret switches its layout. Dropping a card or row on a tab moves the
 * task there; dragging a tab onto another reorders the tabs.
 */
export function ScopeTabs<T extends string>({
  order,
  active,
  counts,
  layouts,
  layoutOf,
  onSelect,
  onReorder,
  onChangeLayout,
  onDropTask,
}: {
  order: TasksScope[];
  active: TasksScope;
  counts: Record<TasksScope, number>;
  layouts: LayoutOption<T>[];
  layoutOf: (scope: TasksScope) => T;
  onSelect: (scope: TasksScope) => void;
  onReorder: (order: TasksScope[]) => void;
  onChangeLayout: (type: T) => void;
  onDropTask: (taskId: string, scope: TasksScope) => void;
}) {
  const [dropTarget, setDropTarget] = useState<TasksScope | null>(null);
  const [dragging, setDragging] = useState<TasksScope | null>(null);
  const optionOf = (scope: TasksScope) => layouts.find((l) => l.type === layoutOf(scope)) ?? layouts[0];

  return (
    <div className="tasks-tabs" role="tablist">
      {order.map((scope) => {
        const Icon = optionOf(scope).icon;
        return (
          <div key={scope} className="tasks-tab-wrap">
            <button
              type="button"
              role="tab"
              aria-selected={scope === active}
              draggable
              title="Drag to reorder the tabs"
              className={cn(
                'tasks-tab',
                scope === active && 'tasks-tab-active',
                dropTarget === scope && 'tasks-tab-drop',
                dragging === scope && 'tasks-tab-dragging',
              )}
              onClick={() => onSelect(scope)}
              onDragStart={(e) => {
                e.dataTransfer.setData(TAB_DRAG_MIME, scope);
                e.dataTransfer.effectAllowed = 'move';
                setDragging(scope);
              }}
              onDragEnd={() => setDragging(null)}
              onDragOver={(e) => {
                const tab = isTabDrag(e);
                if (!tab && (scope === active || !isRecordDrag(e))) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                if (dropTarget !== scope) setDropTarget(scope);
              }}
              onDragLeave={() => setDropTarget(null)}
              onDrop={(e) => {
                setDropTarget(null);
                const moved = e.dataTransfer.getData(TAB_DRAG_MIME) as TasksScope;
                if (moved) {
                  e.preventDefault();
                  onReorder(reorderScopes(order, moved, scope));
                  return;
                }
                const taskId = readDraggedRecordId(e);
                if (!taskId) return;
                e.preventDefault();
                onDropTask(taskId, scope);
              }}
            >
              <Icon size={13} aria-hidden="true" />
              {SCOPE_LABELS[scope]}
              <span className="tasks-tab-count">{counts[scope]}</span>
            </button>
            {scope === active && (
              <Popover
                width="w-44"
                trigger={({ toggle }) => (
                  <button
                    type="button"
                    className="tasks-tab-caret"
                    title="Layout"
                    aria-label="Change layout"
                    onClick={toggle}
                  >
                    <ChevronDown size={12} />
                  </button>
                )}
              >
                {(close) => (
                  <div className="space-y-1">
                    <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Layout
                    </p>
                    {layouts.map(({ type, label, icon: LayoutIcon }) => (
                      <button
                        key={type}
                        type="button"
                        onClick={() => {
                          onChangeLayout(type);
                          close();
                        }}
                        className={cn(
                          'flex w-full items-center gap-2 px-2 py-1.5 text-sm transition-colors',
                          layoutOf(scope) === type
                            ? 'bg-muted text-foreground'
                            : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                        )}
                      >
                        <LayoutIcon size={13} />
                        {label}
                      </button>
                    ))}
                  </div>
                )}
              </Popover>
            )}
          </div>
        );
      })}
    </div>
  );
}
