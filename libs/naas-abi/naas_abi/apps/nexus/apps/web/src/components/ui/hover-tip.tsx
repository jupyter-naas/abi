'use client';

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
  type RefCallback,
} from 'react';
import { createPortal } from 'react-dom';

/**
 * A hover tip with a title and a description, the dock's (`sidebar/index.tsx`): a square box
 * beside its anchor, to the right, else to the left, else under it, always inside the
 * screen. Inside a column marked `data-hover-tip-edge` (the Settings column), it starts at the
 * column's edge, touching it, not at the anchor's. No entrance effect: it shows where it stays. It shows after `delay` (a pickers' tip after a pause), on hover or keyboard focus,
 * and goes on leave, blur, a press, a key, a scroll or a resize; a press keeps it away until
 * the pointer leaves (the picker it explains is open). No tip on a touch screen.
 */

const GAP = 10;
const MARGIN = 8;
/** A tip that just went: the next short-delay one shows at once (moving down a list). */
const WARM_MS = 400;
let lastHidden = 0;

/** A link's tip (the Settings column): after a second of hover. */
export const LINK_TIP_DELAY_MS = 1000;

export type HoverTipPlacement = { top: number; left: number; side: 'right' | 'left' | 'below' };

/** Where a tip of `size` goes beside `anchor`, inside a `viewport`. */
export function placeHoverTip(
  anchor: { top: number; left: number; right: number; bottom: number; height: number },
  size: { width: number; height: number },
  viewport: { width: number; height: number },
  /** Space between the anchor and the tip: none against a column's edge. */
  gap = GAP
): HoverTipPlacement {
  const clampTop = (top: number) => Math.max(MARGIN, Math.min(top, viewport.height - size.height - MARGIN));
  const middle = anchor.top + anchor.height / 2 - size.height / 2;
  if (anchor.right + gap + size.width <= viewport.width - MARGIN) {
    return { top: clampTop(middle), left: anchor.right + gap, side: 'right' };
  }
  if (anchor.left - gap - size.width >= MARGIN) {
    return { top: clampTop(middle), left: anchor.left - gap - size.width, side: 'left' };
  }
  const left = Math.max(MARGIN, Math.min(anchor.left, viewport.width - size.width - MARGIN));
  const below = anchor.bottom + GAP / 2;
  const top = below + size.height <= viewport.height - MARGIN ? below : anchor.top - GAP / 2 - size.height;
  return { top: Math.max(MARGIN, top), left, side: 'below' };
}

function hoverless(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia('(hover: none)').matches
    : false;
}

export type HoverTipAnchorProps = {
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onFocus: () => void;
  onBlur: () => void;
  onPointerDown: () => void;
  onKeyDown: () => void;
  'aria-describedby'?: string;
};

/**
 * The tip of one anchor: spread `anchorProps` on it, give it `ref`, render `tip`. Without a
 * description (or `disabled`) there is no tip.
 */
export function useHoverTip({
  title,
  description,
  delay = LINK_TIP_DELAY_MS,
  disabled = false,
}: {
  title: ReactNode;
  description?: ReactNode;
  delay?: number;
  disabled?: boolean;
}): { ref: RefCallback<HTMLElement>; anchorProps: HoverTipAnchorProps; tip: ReactNode; open: boolean } {
  const id = useId();
  const anchor = useRef<HTMLElement | null>(null);
  const box = useRef<HTMLDivElement | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pressed = useRef(false);
  const [open, setOpen] = useState(false);
  const [place, setPlace] = useState<HoverTipPlacement | null>(null);
  const active = !disabled && !!description;

  const cancel = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };
  const hide = useCallback(() => {
    cancel();
    setOpen((was) => {
      if (was) lastHidden = Date.now();
      return false;
    });
    setPlace(null);
  }, []);
  const show = () => {
    if (!active || pressed.current || hoverless()) return;
    cancel();
    const warm = delay <= LINK_TIP_DELAY_MS && Date.now() - lastHidden < WARM_MS;
    if (warm || delay <= 0) setOpen(true);
    else timer.current = setTimeout(() => setOpen(true), delay);
  };

  // Measured once shown (hidden until placed), then kept inside the screen.
  useLayoutEffect(() => {
    if (!open || !anchor.current || !box.current) return;
    const own = anchor.current.getBoundingClientRect();
    const edge = anchor.current.closest('[data-hover-tip-edge]')?.getBoundingClientRect();
    const rect = edge
      ? { top: own.top, height: own.height, bottom: own.bottom, left: edge.left, right: edge.right }
      : own;
    const size = box.current.getBoundingClientRect();
    setPlace(
      placeHoverTip(
        rect,
        { width: size.width, height: size.height },
        { width: window.innerWidth, height: window.innerHeight },
        // Against the column's edge: touching it.
        edge ? 0 : GAP
      )
    );
  }, [open]);

  useEffect(() => {
    if (!open) return;
    window.addEventListener('scroll', hide, true);
    window.addEventListener('resize', hide);
    return () => {
      window.removeEventListener('scroll', hide, true);
      window.removeEventListener('resize', hide);
    };
  }, [open, hide]);
  useEffect(() => cancel, []);
  useEffect(() => {
    if (!active) hide();
  }, [active, hide]);

  const ref = useCallback<RefCallback<HTMLElement>>((node) => {
    anchor.current = node;
  }, []);

  const anchorProps: HoverTipAnchorProps = {
    onMouseEnter: show,
    onMouseLeave: () => {
      pressed.current = false;
      hide();
    },
    onFocus: show,
    onBlur: hide,
    onPointerDown: () => {
      pressed.current = true;
      hide();
    },
    onKeyDown: hide,
    ...(open ? { 'aria-describedby': id } : {}),
  };

  const tip =
    open && typeof document !== 'undefined'
      ? createPortal(
          <div
            ref={box}
            id={id}
            role="tooltip"
            data-hover-tip={place?.side ?? ''}
            className="pointer-events-none fixed z-[500] w-64 max-w-[calc(100vw-16px)] border border-border bg-background px-3 py-2 shadow-lg"
            style={{ top: place?.top ?? 0, left: place?.left ?? 0, visibility: place ? 'visible' : 'hidden', transition: 'none' }}
          >
            <p className="text-sm font-medium text-foreground">{title}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          </div>,
          document.body
        )
      : null;

  return { ref, anchorProps, tip, open };
}
