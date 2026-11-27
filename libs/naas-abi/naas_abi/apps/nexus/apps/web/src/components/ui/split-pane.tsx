'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

export function useColumnResize(width: number, setWidth: (next: number) => void) {
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);
  const isDraggingRef = useRef(false);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const delta = e.clientX - dragStartX.current;
      setWidth(dragStartWidth.current + delta);
    };
    const onUp = () => {
      if (!isDraggingRef.current) return;
      isDraggingRef.current = false;
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [setWidth]);

  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      isDraggingRef.current = true;
      setIsDragging(true);
      dragStartX.current = e.clientX;
      dragStartWidth.current = width;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    },
    [width],
  );

  return { isDragging, handleDragStart };
}

export function ColumnResizeHandle({
  onMouseDown,
  label,
  isActive,
}: {
  onMouseDown: (e: React.MouseEvent) => void;
  label: string;
  /**
   * True while a drag is in progress. A full-screen overlay captures the
   * cursor during the drag so the pointer is no longer technically "over"
   * this handle, which drops CSS :hover — so the highlighted state has to be
   * driven from drag state too, not just group-hover.
   */
  isActive?: boolean;
}) {
  return (
    <div
      className="group relative flex w-0.5 shrink-0 cursor-col-resize items-center justify-center"
      onMouseDown={onMouseDown}
      title={label}
      aria-label={label}
      role="separator"
      aria-orientation="vertical"
    >
      <div
        className={cn(
          'h-full transition-all',
          isActive
            ? 'w-0.5 bg-black dark:bg-white'
            : 'w-px bg-border group-hover:w-0.5 group-hover:bg-black dark:group-hover:bg-white',
        )}
      />
    </div>
  );
}
