'use client';

import { useState, useEffect, useRef, useCallback, useMemo, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Notice } from '@/components/ui/notice';
import { Spinner } from '@/components/ui/spinner';
import { useAgentsStore, type Agent } from '@/stores/agents';
import { useWorkspaceStore } from '@/stores/workspace';

// ============================================================
// Generic Modal Backdrop
// ============================================================

export function ModalBackdrop({
  open,
  onClose,
  children,
  widthClassName = 'max-w-md',
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  /** Content width; prompts use the default, previews go wider. */
  widthClassName?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      // An Escape a field inside has used (a list it closed) leaves the modal open.
      if (e.key === 'Escape' && !e.defaultPrevented) onClose();
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
      <div className={cn('relative z-10 mx-4 w-full animate-in zoom-in-95 fade-in duration-200', widthClassName)}>
        {children}
      </div>
    </div>,
    document.body
  );
}

// ============================================================
// useAgentList - same list as chat page (AgentSelector)
// Use this in any dialog that needs to show or select agents.
// ============================================================

export function useAgentList(searchQuery = '') {
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const { agents, fetchAgents, getAgent } = useAgentsStore();

  // The API lists exactly the agents the caller may use in the workspace.
  const usableAgents = agents;

  const filteredAgents = useMemo(
    () =>
      searchQuery.trim()
        ? usableAgents.filter(
            (a: Agent) =>
              a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
              a.description.toLowerCase().includes(searchQuery.toLowerCase())
          )
        : usableAgents,
    [usableAgents, searchQuery]
  );

  const defaultAgents = useMemo(
    () =>
      filteredAgents
        .filter((a: Agent) => a.isDefault)
        .sort((a: Agent, b: Agent) => a.name.localeCompare(b.name)),
    [filteredAgents]
  );

  const customAgents = useMemo(
    () =>
      filteredAgents
        .filter((a: Agent) => !a.isDefault)
        .sort((a: Agent, b: Agent) => a.name.localeCompare(b.name)),
    [filteredAgents]
  );

  useEffect(() => {
    if (currentWorkspaceId) {
      fetchAgents(currentWorkspaceId);
    }
  }, [currentWorkspaceId, fetchAgents]);

  return {
    usableAgents,
    defaultAgents,
    customAgents,
    filteredAgents,
    getAgent,
  } as const;
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
      requestAnimationFrame(() => inputRef.current?.select());
    }
  }, [open, defaultValue]);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    const err = !trimmed ? 'Name cannot be empty' : (validate?.(trimmed) ?? null);
    if (err) setError(err);
    else onConfirm(trimmed);
  }, [value, validate, onConfirm]);

  return (
    <Dialog
      open={open}
      title={title}
      description={description}
      onClose={onCancel}
      onSubmit={handleSubmit}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button onClick={handleSubmit}>{confirmLabel}</Button>
        </>
      }
    >
      <Field label={title} error={error} className="[&>label]:sr-only">
        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSubmit();
          }}
          placeholder={placeholder}
          aria-invalid={error ? true : undefined}
          className={cn(error && 'border-destructive')}
          data-autofocus
        />
      </Field>
    </Dialog>
  );
}

// ============================================================
// ConfirmDialog - replaces window.confirm
// ============================================================

/**
 * Asks before an action. With `confirmText`, the action stays disabled until that text is
 * typed (type-to-confirm, for what cannot be undone). `busy` and `error` let an async
 * action keep the dialog open while it runs and say why it failed.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  destructive = true,
  confirmText,
  busy = false,
  error,
  children,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  confirmText?: string;
  busy?: boolean;
  error?: ReactNode;
  children?: ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [typed, setTyped] = useState('');
  useEffect(() => {
    if (open) setTyped('');
  }, [open]);
  const ready = !busy && (!confirmText || typed.trim() === confirmText);
  const confirm = () => {
    if (ready) onConfirm();
  };
  return (
    <Dialog
      open={open}
      size="sm"
      title={title}
      tone={destructive ? 'danger' : 'neutral'}
      onClose={onCancel}
      onSubmit={confirm}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={destructive ? 'destructive' : 'primary'} disabled={!ready} onClick={confirm}>
            {busy ? <Spinner size={14} /> : null}
            {confirmLabel}
          </Button>
        </>
      }
    >
      {description ? <p className="whitespace-pre-line text-muted-foreground">{description}</p> : null}
      {children}
      {confirmText ? (
        <Field label={<>Type <code className="font-mono">{confirmText}</code> to confirm</>}>
          <Input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') confirm();
            }}
            autoComplete="off"
            spellCheck={false}
            data-autofocus
          />
        </Field>
      ) : null}
      {error ? <Notice tone="error">{error}</Notice> : null}
    </Dialog>
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
  confirmText?: string;
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
      /** Type-to-confirm: the text the person must type first. */
      confirmText?: string;
    }): Promise<boolean> => {
      return new Promise((resolve) => {
        setState({
          open: true,
          title: opts.title,
          description: opts.description,
          confirmLabel: opts.confirmLabel || 'Delete',
          destructive: opts.destructive ?? true,
          confirmText: opts.confirmText,
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
      confirmText={state.confirmText}
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
