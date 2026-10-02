'use client';

/** Short confirmations and failures, bottom right, gone after a few seconds. */
import { useCallback, useState } from 'react';
import { AlertTriangle, CheckCircle2, X } from 'lucide-react';

export interface Toast {
  id: number;
  tone: 'success' | 'danger';
  title: string;
  detail?: string;
}

let next = 1;

export function useToasts(timeoutMs = 4200) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), []);
  const push = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = next++;
      setToasts((all) => [...all.slice(-3), { ...toast, id }]);
      window.setTimeout(() => dismiss(id), toast.tone === 'danger' ? timeoutMs * 2 : timeoutMs);
    },
    [dismiss, timeoutMs],
  );
  return { toasts, push, dismiss };
}

export function ToastStack({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: number) => void }) {
  return (
    <div className="data-toasts" role="region" aria-label="Notifications" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`data-toast data-toast-${t.tone}`}>
          {t.tone === 'success' ? (
            <CheckCircle2 size={16} aria-hidden="true" />
          ) : (
            <AlertTriangle size={16} aria-hidden="true" />
          )}
          <div className="data-toast-body">
            <p className="data-toast-title">{t.title}</p>
            {t.detail && <p className="data-toast-detail">{t.detail}</p>}
          </div>
          <button type="button" className="data-icon-button" aria-label="Dismiss" onClick={() => dismiss(t.id)}>
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>
  );
}
