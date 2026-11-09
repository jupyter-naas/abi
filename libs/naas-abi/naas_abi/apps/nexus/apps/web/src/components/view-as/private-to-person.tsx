'use client';

import { useAuthStore } from '@/stores/auth';
import './view-banner.css';

/** The name of the person whose view this is, or null outside a view. */
export function usePrivateTo(): string | null {
  return useAuthStore((s) => s.view?.person.name ?? null);
}

/**
 * What a page of the person's own shows in a view instead of their content: it stays private to
 * them, and the page asks the server for nothing (the server answers these empty in a view anyway).
 */
export function PrivateToPerson({ what }: { what?: string }) {
  const name = usePrivateTo();
  if (!name) return null;
  return (
    <div className="view-private" role="status" data-private-to={name}>
      <p className="view-private-title">Private to {name}</p>
      <p className="view-private-note">
        {what ? `${what}: ` : ''}nothing of it is shown in a view.
      </p>
    </div>
  );
}

/**
 * A page of the person's own: its children in the viewer's own session, "Private to <name>" in a
 * view. The children are not rendered then, so they ask the server for nothing.
 */
export function PrivateGate({ what, children }: { what?: string; children: React.ReactNode }) {
  const name = usePrivateTo();
  return name ? <PrivateToPerson what={what} /> : <>{children}</>;
}
