'use client';

/** A centered dialog: focus stays inside, Escape closes, ⌘/Ctrl+Enter submits. */
import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

export function Modal({
  title,
  subtitle,
  icon,
  tone = 'neutral',
  size = 'md',
  onClose,
  onSubmit,
  footer,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  icon?: ReactNode;
  tone?: 'neutral' | 'danger';
  size?: 'md' | 'lg' | 'xl';
  onClose: () => void;
  onSubmit?: () => void;
  footer?: ReactNode;
  children: ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const restore = useRef<HTMLElement | null>(null);

  useEffect(() => {
    restore.current = document.activeElement as HTMLElement | null;
    const first = panel.current?.querySelector<HTMLElement>('[data-autofocus], input, textarea, button');
    first?.focus();
    return () => restore.current?.focus?.();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose();
      } else if (onSubmit && (event.metaKey || event.ctrlKey) && (event.key === 'Enter' || event.key === 's')) {
        event.preventDefault();
        onSubmit();
      } else if (event.key === 'Tab' && panel.current) {
        const focusable = panel.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select, [tabindex="0"]',
        );
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
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [onClose, onSubmit]);

  return createPortal(
    <div className="data-modal-root">
      <div className="data-modal-backdrop" onClick={onClose} aria-hidden="true" />
      <div
        ref={panel}
        className={`data-modal data-modal-${size} data-modal-${tone}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header className="data-modal-header">
          {icon && <span className="data-modal-icon">{icon}</span>}
          <div className="data-modal-heading">
            <h2 className="data-modal-title">{title}</h2>
            {subtitle && <p className="data-modal-subtitle">{subtitle}</p>}
          </div>
          <button type="button" className="data-icon-button" aria-label="Close" onClick={onClose}>
            <X size={16} aria-hidden="true" />
          </button>
        </header>
        <div className="data-modal-body">{children}</div>
        {footer && <footer className="data-modal-footer">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}
