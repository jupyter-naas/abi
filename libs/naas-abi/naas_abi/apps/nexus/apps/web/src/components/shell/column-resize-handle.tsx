'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

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
}: {
  onMouseDown: (e: React.MouseEvent) => void;
  label: string;
}) {
  return (
    <div
      className="group relative flex w-2 shrink-0 cursor-col-resize items-center justify-center"
      onMouseDown={onMouseDown}
      title={label}
      aria-label={label}
      role="separator"
      aria-orientation="vertical"
    >
      <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border transition-colors group-hover:bg-workspace-accent" />
      <div className="relative z-10 flex flex-col gap-[5px]">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-[3px] w-[3px] rounded-full bg-muted-foreground/40 transition-colors group-hover:bg-workspace-accent"
          />
        ))}
      </div>
    </div>
  );
}
