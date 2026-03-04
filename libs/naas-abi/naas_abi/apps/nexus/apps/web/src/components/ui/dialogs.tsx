'use client';

import { useState, useEffect, useRef, useCallback, createContext, useContext, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';

// ============================================================
// Generic Modal Backdrop
// ============================================================

function ModalBackdrop({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
      />
      {/* Content */}
      <div className="relative z-10 w-full max-w-md mx-4 animate-in zoom-in-95 fade-in duration-200">
        {children}
      </div>
    </div>,
    document.body
  );
}

// ============================================================
// PromptDialog - replaces window.prompt
// ============================================================

export function PromptDialog({
  open,
  title,
  description,
  placeholder,
  defaultValue = '',
  confirmLabel = 'Create',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  validate,
}: {
  open: boolean;
  title: string;
  description?: string;
  placeholder?: string;
  defaultValue?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: (value: string) => void;
  onCancel: () => void;
  validate?: (value: string) => string | null; // returns error message or null
}) {
  const [value, setValue] = useState(defaultValue);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setValue(defaultValue);
      setError(null);
      // Focus input after animation
      requestAnimationFrame(() => inputRef.current?.select());
    }
  }, [open, defaultValue]);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed) {
      setError('Name cannot be empty');
      return;
    }
    if (validate) {
      const err = validate(trimmed);
      if (err) {
        setError(err);
        return;
      }
    }
    onConfirm(trimmed);
  }, [value, validate, onConfirm]);

  return (
    <ModalBackdrop open={open} onClose={onCancel}>
      <div className="rounded-xl border border-border bg-background p-6 shadow-2xl">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSubmit();
          }}
          placeholder={placeholder}
          className={cn(
            'mt-4 w-full rounded-lg border bg-muted/50 px-3 py-2 text-sm text-foreground',
            'outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-workspace-accent focus-visible:ring-offset-2',
            error ? 'border-red-500' : 'border-border'
          )}
          autoFocus
        />
        {error && (
          <p className="mt-1 text-xs text-red-500">{error}</p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-lg px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {cancelLabel}
          </button>
          <button
            onClick={handleSubmit}
            className="rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-workspace-accent/90"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </ModalBackdrop>
  );
}

// ============================================================
// ConfirmDialog - replaces window.confirm
// ============================================================

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  destructive = true,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <ModalBackdrop open={open} onClose={onCancel}>
      <div className="rounded-xl border border-border bg-background p-6 shadow-2xl">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        {description && (
          <p className="mt-2 text-sm text-muted-foreground">{description}</p>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-lg px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={cn(
              'rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors',
              destructive
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-workspace-accent hover:bg-workspace-accent/90'
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </ModalBackdrop>
  );
}

// ============================================================
// usePrompt / useConfirm hooks for easy usage
// ============================================================

interface PromptState {
  open: boolean;
  title: string;
  description?: string;
  placeholder?: string;
  defaultValue: string;
  confirmLabel: string;
  resolve: ((value: string | null) => void) | null;
}

export function usePrompt() {
  const [state, setState] = useState<PromptState>({
    open: false,
    title: '',
    defaultValue: '',
    confirmLabel: 'Create',
    resolve: null,
  });

  const prompt = useCallback(
    (opts: {
      title: string;
      description?: string;
      placeholder?: string;
      defaultValue?: string;
      confirmLabel?: string;
    }): Promise<string | null> => {
      return new Promise((resolve) => {
        setState({
          open: true,
          title: opts.title,
          description: opts.description,
          placeholder: opts.placeholder,
          defaultValue: opts.defaultValue || '',
          confirmLabel: opts.confirmLabel || 'Create',
          resolve,
        });
      });
    },
    []
  );

  const dialog = (
    <PromptDialog
      open={state.open}
      title={state.title}
      description={state.description}
      placeholder={state.placeholder}
      defaultValue={state.defaultValue}
      confirmLabel={state.confirmLabel}
      onConfirm={(value) => {
        state.resolve?.(value);
        setState((s) => ({ ...s, open: false, resolve: null }));
      }}
      onCancel={() => {
        state.resolve?.(null);
        setState((s) => ({ ...s, open: false, resolve: null }));
      }}
    />
  );

  return { prompt, dialog };
}

interface ConfirmState {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel: string;
  destructive: boolean;
  resolve: ((value: boolean) => void) | null;
}

export function useConfirm() {
  const [state, setState] = useState<ConfirmState>({
    open: false,
    title: '',
    confirmLabel: 'Delete',
    destructive: true,
    resolve: null,
  });

  const confirm = useCallback(
    (opts: {
      title: string;
      description?: string;
      confirmLabel?: string;
      destructive?: boolean;
    }): Promise<boolean> => {
      return new Promise((resolve) => {
        setState({
          open: true,
          title: opts.title,
          description: opts.description,
          confirmLabel: opts.confirmLabel || 'Delete',
          destructive: opts.destructive ?? true,
          resolve,
        });
      });
    },
    []
  );

  const dialog = (
    <ConfirmDialog
      open={state.open}
      title={state.title}
      description={state.description}
      confirmLabel={state.confirmLabel}
      destructive={state.destructive}
      onConfirm={() => {
        state.resolve?.(true);
        setState((s) => ({ ...s, open: false, resolve: null }));
      }}
      onCancel={() => {
        state.resolve?.(false);
        setState((s) => ({ ...s, open: false, resolve: null }));
      }}
    />
  );

  return { confirm, dialog };
}
