'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Eye, X } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { endView } from '@/lib/view-as';
import { minutesLeft, navigation, onViewRefusal } from '@/lib/view-model';
import './view-banner.css';

/** How often the minutes left are redrawn. */
const TICK_MS = 15_000;
const TOAST_MS = 8_000;

type Toast = { id: number; message: string };
let nextToast = 1;

/**
 * The banner of a view ("View as"), on every page of every shell (it is in the root layout):
 * "Viewing as <name> (read-only) in <workspace> · <n> min left · Stop". The view is the server's
 * (`GET /api/auth/oidc/session`, `view`); when it ends the page reloads by itself, and Stop reloads
 * to the person's page. The server's refusals ("Read-only: ...", "Outside this view: ...") are
 * shown here as toasts, as the server words them.
 */
export function ViewBanner() {
  const view = useAuthStore((s) => s.view);
  const provider = useAuthStore((s) => s.provider);
  const [now, setNow] = useState(() => Date.now());
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const endsAt = view?.ends_at ?? null;

  // The minutes left, and the reload at the end.
  useEffect(() => {
    if (!endsAt) return;
    setNow(Date.now());
    const tick = window.setInterval(() => setNow(Date.now()), TICK_MS);
    const left = new Date(endsAt).getTime() - Date.now();
    const end = window.setTimeout(() => navigation.reload(), Math.min(Math.max(left, 0), 2 ** 31 - 1));
    return () => {
      window.clearInterval(tick);
      window.clearTimeout(end);
    };
  }, [endsAt]);

  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), []);
  useEffect(
    () =>
      onViewRefusal((message) => {
        const id = nextToast++;
        setToasts((all) => [...all.slice(-2), { id, message }]);
        window.setTimeout(() => dismiss(id), TOAST_MS);
      }),
    [dismiss],
  );

  if (!view) return null;

  const stop = async () => {
    setStopping(true);
    setError(null);
    try {
      await endView(view);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStopping(false);
    }
  };

  return (
    <>
      <div className="view-banner" role="status" data-view-banner="">
        <Eye size={14} aria-hidden="true" />
        <span className="view-banner-text">
          Viewing as <strong>{view.person.name}</strong> (read-only) in <strong>{view.workspace.name}</strong>
          {' · '}
          {minutesLeft(view.ends_at, now)} min left
          {view.groups_from === null && <> · without {provider || 'identity provider'} groups</>}
        </span>
        {error && (
          <span className="view-banner-error" role="alert">
            {error}
          </span>
        )}
        <button type="button" className="view-banner-stop" disabled={stopping} onClick={() => void stop()}>
          Stop
        </button>
      </div>
      {toasts.length > 0 && (
        <div className="view-toasts" role="region" aria-label="Notifications" aria-live="polite">
          {toasts.map((t) => (
            <div key={t.id} className="view-toast" data-view-toast="">
              <AlertTriangle size={16} aria-hidden="true" />
              <p className="view-toast-message">{t.message}</p>
              <button type="button" className="view-toast-close" aria-label="Dismiss" onClick={() => dismiss(t.id)}>
                <X size={14} aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
