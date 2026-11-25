'use client';

import { useEffect, useId, useRef, type HTMLAttributes, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

const widths = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  full: 'max-w-[calc(100vw-4rem)] h-[calc(100vh-4rem)]',
} as const;

export type DialogSize = keyof typeof widths;

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * The one dialog, in five widths. Focus moves in (to `[data-autofocus]`, else the first
 * field or button) and back out on close, Tab stays inside, Escape closes (unless a field
 * inside already used it), ⌘/Ctrl+Enter submits when `onSubmit` is given. While an action runs,
 * `dismissible={false}` keeps it open (no Escape, backdrop or close button). Other attributes
 * (`data-*`, `id`) go on the dialog element.
 */
export function Dialog({
  open = true,
  title,
  description,
  icon,
  tone = 'neutral',
  size = 'md',
  onClose,
  onSubmit,
  footer,
  children,
  className,
  dismissible = true,
  ...rest
}: Omit<HTMLAttributes<HTMLDivElement>, 'title' | 'onSubmit'> & {
  open?: boolean;
  title: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
  tone?: 'neutral' | 'danger';
  size?: DialogSize;
  onClose: () => void;
  onSubmit?: () => void;
  /** Buttons, right-aligned; a leading hint can sit first (it takes the free space). */
  footer?: ReactNode;
  children?: ReactNode;
  className?: string;
  /** False while something runs that closing would interrupt. */
  dismissible?: boolean;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const close = useRef(dismissible ? onClose : () => undefined);
  const submit = useRef(onSubmit);
  close.current = dismissible ? onClose : () => undefined;
  submit.current = onSubmit;

  useEffect(() => {
    if (!open) return;
    const restore = document.activeElement as HTMLElement | null;
    const target =
      panel.current?.querySelector<HTMLElement>('[data-autofocus]') ??
      panel.current?.querySelector<HTMLElement>('input, textarea, select') ??
      panel.current?.querySelector<HTMLElement>('[data-dialog-body] button, footer button');
    (target ?? panel.current)?.focus();

    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) {
        event.stopPropagation();
        close.current();
      } else if (submit.current && (event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        submit.current();
      } else if (event.key === 'Tab' && panel.current) {
        const focusable = panel.current.querySelectorAll<HTMLElement>(FOCUSABLE);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      restore?.focus?.();
    };
  }, [open]);

  if (!open || typeof document === 'undefined') return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
      <div
        aria-hidden="true"
        onClick={() => close.current()}
        className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
      />
      <div
        {...rest}
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={rest['aria-label'] ?? (typeof title === 'string' ? title : undefined)}
        aria-labelledby={rest['aria-label'] || typeof title === 'string' ? undefined : titleId}
        tabIndex={-1}
        className={cn(
          'relative z-10 flex max-h-full w-full flex-col border border-border bg-background shadow-2xl outline-none animate-in zoom-in-95 fade-in duration-200',
          widths[size],
          className
        )}
      >
        <header className="flex items-start gap-3 px-5 pb-3 pt-5">
          {icon ? (
            <span className={cn('mt-0.5 shrink-0', tone === 'danger' ? 'text-destructive' : 'text-muted-foreground')}>
              {icon}
            </span>
          ) : null}
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-base font-semibold text-foreground">{title}</h2>
            {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
          </div>
          <button
            type="button"
            aria-label="Close"
            data-action="close"
            disabled={!dismissible}
            onClick={onClose}
            className="-mr-1 -mt-1 inline-flex h-8 w-8 shrink-0 items-center justify-center text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
          >
            <X size={16} />
          </button>
        </header>
        {children ? (
          <div data-dialog-body className="min-h-0 flex-1 space-y-3 overflow-auto px-5 pb-4 text-sm">
            {children}
          </div>
        ) : null}
        {footer ? (
          <footer className="flex items-center justify-end gap-2 border-t border-border px-5 py-3 [&>:first-child:not(button)]:mr-auto">
            {footer}
          </footer>
        ) : null}
      </div>
    </div>,
    document.body
  );
}
