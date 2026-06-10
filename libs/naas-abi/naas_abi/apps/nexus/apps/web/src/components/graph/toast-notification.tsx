'use client';

import { useEffect } from 'react';
import { AlertCircle, CheckCircle2, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ToastItem {
  id: string;
  type: 'success' | 'error';
  title: string;
  message?: string;
}

export function ToastStack({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;
  return (
    <div className="pointer-events-none fixed right-4 top-4 z-[9999] flex flex-col gap-2">
      {toasts.map((toast) => (
        <SingleToast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function SingleToast({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: string) => void;
}) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(toast.id), 4500);
    return () => clearTimeout(t);
  }, [toast.id, onDismiss]);

  const ok = toast.type === 'success';

  return (
    <div
      className={cn(
        'pointer-events-auto flex min-w-[280px] max-w-sm items-start gap-3 rounded-lg border p-3.5 shadow-lg',
        ok
          ? 'border-green-200 bg-green-50 text-green-900 dark:border-green-800 dark:bg-green-950 dark:text-green-100'
          : 'border-red-200 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-100',
      )}
    >
      {ok ? (
        <CheckCircle2
          size={15}
          className="mt-0.5 shrink-0 text-green-600 dark:text-green-400"
        />
      ) : (
        <AlertCircle
          size={15}
          className="mt-0.5 shrink-0 text-red-600 dark:text-red-400"
        />
      )}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{toast.title}</p>
        {toast.message && (
          <p className="mt-0.5 truncate text-xs opacity-80">{toast.message}</p>
        )}
      </div>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        className="shrink-0 rounded p-0.5 opacity-60 hover:opacity-100"
      >
        <X size={12} />
      </button>
    </div>
  );
}

export function useToasts() {
  return {
    push: (toast: Omit<ToastItem, 'id'>): ToastItem => ({
      ...toast,
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    }),
  };
}
