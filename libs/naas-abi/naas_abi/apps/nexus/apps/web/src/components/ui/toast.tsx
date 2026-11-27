'use client';

import { useSyncExternalStore } from 'react';
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Short confirmations and failures, bottom right, gone after a few seconds (failures stay
 * twice as long). One stack for the whole app: `<Toaster />` is mounted once in the root
 * layout, and any component calls `toast(...)`. Nothing to mount, no hook to thread.
 */
export type ToastTone = 'success' | 'error' | 'info';

export interface Toast {
  id: number;
  tone: ToastTone;
  title: string;
  detail?: string;
}

const TIMEOUT_MS = 4200;
const MAX_VISIBLE = 4;

let toasts: Toast[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit(next: Toast[]) {
  toasts = next;
  listeners.forEach((listener) => listener());
}

export function dismissToast(id: number) {
  emit(toasts.filter((t) => t.id !== id));
}

/** Shows a toast and returns its id. */
export function toast(input: Omit<Toast, 'id' | 'tone'> & { tone?: ToastTone }): number {
  const id = nextId++;
  const item: Toast = { tone: 'info', ...input, id };
  emit([...toasts.slice(-(MAX_VISIBLE - 1)), item]);
  if (typeof window !== 'undefined') {
    window.setTimeout(() => dismissToast(id), item.tone === 'error' ? TIMEOUT_MS * 2 : TIMEOUT_MS);
  }
  return id;
}

toast.success = (title: string, detail?: string) => toast({ tone: 'success', title, detail });
toast.error = (title: string, detail?: string) => toast({ tone: 'error', title, detail });

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

const EMPTY: Toast[] = [];

/** The current toasts (for the Toaster, and for tests). */
export function useToastList(): Toast[] {
  return useSyncExternalStore(subscribe, () => toasts, () => EMPTY);
}

const icons = { success: CheckCircle2, error: AlertTriangle, info: Info } as const;
const iconTone = { success: 'text-primary', error: 'text-destructive', info: 'text-muted-foreground' } as const;

export function Toaster() {
  const list = useToastList();
  return (
    <div
      role="region"
      aria-label="Notifications"
      aria-live="polite"
      className="pointer-events-none fixed bottom-4 right-4 z-[10000] flex w-[22rem] max-w-[calc(100vw-2rem)] flex-col gap-2"
    >
      {list.map((t) => {
        const Icon = icons[t.tone];
        return (
          <div
            key={t.id}
            role={t.tone === 'error' ? 'alert' : 'status'}
            data-tone={t.tone}
            className="pointer-events-auto flex items-start gap-3 border border-border bg-card p-3 text-card-foreground shadow-lg animate-in fade-in slide-in-from-bottom-2"
          >
            <Icon size={16} aria-hidden="true" className={cn('mt-0.5 shrink-0', iconTone[t.tone])} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{t.title}</p>
              {t.detail ? <p className="mt-0.5 break-words text-xs text-muted-foreground">{t.detail}</p> : null}
            </div>
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => dismissToast(t.id)}
              className="shrink-0 text-muted-foreground hover:text-foreground"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
