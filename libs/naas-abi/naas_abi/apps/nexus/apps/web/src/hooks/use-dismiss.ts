'use client';

import { useEffect, useRef } from 'react';

/**
 * Closes a menu on an outside click, on focus leaving it (Tab), or on Escape, which hands
 * the focus back to its trigger (`setOpen` is a state setter: stable).
 */
export function useDismiss(open: boolean, setOpen: (open: boolean) => void) {
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const outside = (target: EventTarget | null) =>
      !!ref.current && !(target instanceof Node && ref.current.contains(target));
    const onDown = (e: MouseEvent) => {
      if (outside(e.target)) setOpen(false);
    };
    const onFocus = (e: FocusEvent) => {
      if (outside(e.target)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('focusin', onFocus);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('focusin', onFocus);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, setOpen]);
  return { ref, triggerRef };
}
