import type { DragEvent } from 'react';

/** Rows dragged out of a database view carry their id under this type. */
const DRAG_MIME = 'application/x-nexus-database-row';

export function startRowDrag(e: DragEvent<HTMLElement>, id: string) {
  e.dataTransfer.setData(DRAG_MIME, id);
  e.dataTransfer.effectAllowed = 'move';
}

/** Whether a drag carries a database row, for drop targets outside the body. */
export function isRecordDrag(e: DragEvent<HTMLElement>): boolean {
  return Array.from(e.dataTransfer.types).includes(DRAG_MIME);
}

/** The dragged row's id on drop, or null when the drag is something else. */
export function readDraggedRecordId(e: DragEvent<HTMLElement>): string | null {
  return e.dataTransfer.getData(DRAG_MIME) || null;
}
