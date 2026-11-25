'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Search, UsersRound, KeyRound } from 'lucide-react';
import { Dialog } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import type { PrincipalKind } from '@/lib/iam-admin/types';

/** Someone a policy may be attached to, as the dialog lists them. */
export type AttachCandidate = { id: string; label: string; kind?: PrincipalKind; email?: string | null };

const KIND_LABEL: Partial<Record<PrincipalKind, string>> = { group: 'Group', service_account: 'Service account' };

/** Whether `candidate` answers `query`: every word in its name, email or id. */
export function matchesCandidate(candidate: AttachCandidate, query: string): boolean {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const text = [candidate.label, candidate.email ?? '', candidate.id].join(' ').toLowerCase();
  return words.every((word) => text.includes(word));
}

/**
 * A policy's page › Attach: whom to attach it to, searched by name, email or id among the
 * people, groups and (at the platform) service accounts it may be attached to here, as Invite
 * user searches the people. A pick attaches it at once (`onAttach`); a refusal stays in the
 * dialog. An IAM id typed that is not listed may be attached too, when `typed` offers it.
 */
export function AttachDialog({
  open,
  title,
  where,
  candidates,
  typed,
  onClose,
  onAttach,
  description,
}: {
  open: boolean;
  title: string;
  /** What a pick does; by default, the policy attached at `where`. */
  description?: ReactNode;
  /** Where it is attached: the page's level, named. */
  where: string;
  candidates: AttachCandidate[];
  /** An id typed, when it is one the policy may be attached to (else null). */
  typed?: (id: string) => AttachCandidate | null;
  onClose: () => void;
  onAttach: (candidate: AttachCandidate) => Promise<void>;
}) {
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setBusy(null);
    setError('');
  }, [open]);

  const shown = useMemo(() => {
    const found = candidates.filter((c) => matchesCandidate(c, query)).sort((a, b) => a.label.localeCompare(b.label));
    const id = query.trim();
    const extra = id && !candidates.some((c) => c.id === id) ? typed?.(id) : null;
    return extra ? [extra, ...found] : found;
  }, [candidates, query, typed]);

  const pick = async (candidate: AttachCandidate) => {
    setBusy(candidate.id);
    setError('');
    try {
      await onAttach(candidate);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not attach it');
    } finally {
      setBusy(null);
    }
  };

  return (
    <Dialog
      open={open}
      size="lg"
      title={title}
      description={description ?? <>Type a name, an email or an id. The policy is attached to whom you pick, at {where}.</>}
      onClose={onClose}
      data-attach-dialog=""
    >
      <div className="relative">
        <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search a person, a group or a service account"
          aria-label="Search whom to attach it to"
          className="pl-9"
          data-field="attach-search"
        />
      </div>
      <ul className="max-h-80 overflow-y-auto border border-border" data-attach-options="">
        {shown.length === 0 && (
          <li className="px-3 py-4 text-sm text-muted-foreground">
            {candidates.length === 0 ? 'Nobody it may be attached to here.' : 'Nobody matches.'}
          </li>
        )}
        {shown.map((candidate) => (
          <li key={candidate.id} className="border-b border-border last:border-b-0" data-attach-option={candidate.id}>
            <button
              type="button"
              className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-muted/50 disabled:opacity-50"
              disabled={busy !== null}
              onClick={() => void pick(candidate)}
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center bg-muted text-sm text-muted-foreground">
                {candidate.kind === 'group' ? (
                  <UsersRound size={14} />
                ) : candidate.kind === 'service_account' ? (
                  <KeyRound size={14} />
                ) : (
                  (candidate.label.charAt(0) || '?').toUpperCase()
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground">{candidate.label}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {candidate.email || (candidate.kind && KIND_LABEL[candidate.kind]) || candidate.id}
                </span>
              </span>
              {busy === candidate.id && <span className="text-xs text-muted-foreground">Attaching…</span>}
            </button>
          </li>
        ))}
      </ul>
      {error && (
        <p className="text-xs text-destructive" role="alert" data-attach-error="">
          {error}
        </p>
      )}
    </Dialog>
  );
}
