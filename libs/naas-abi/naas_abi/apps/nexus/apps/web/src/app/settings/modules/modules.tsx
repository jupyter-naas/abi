'use client';

import './modules.css';

import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { createIamAdminApi, type IamAdminApi } from '@/lib/iam-admin/api';
import type { OrganizationSetView, SetsView } from '@/lib/iam-admin/types';
import { SystemFrame, SystemRefresh } from '../system/system';
import { SetsMatrix } from './sets-matrix';
import { partSummary, type SetCatalog } from './sets-model';

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

/**
 * Every organization's set, each expandable to its matrix (the organization, then its
 * workspaces). The platform admin edits an organization's set here; what each column may change
 * is the API's `editable`.
 */
export function ModulesSetsView({ api, nonce = 0 }: { api: IamAdminApi; nonce?: number }) {
  const [view, setView] = useState<SetsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .sets()
      .then((next) => {
        if (cancelled) return;
        setView(next);
        // One organization: open it.
        if (next.organizations.length === 1) setOpen(new Set([next.organizations[0].id]));
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [api, nonce]);

  const catalog: SetCatalog | null = useMemo(
    () => (view ? { modules: view.modules, features: view.features } : null),
    [view],
  );

  const replace = (organization: OrganizationSetView) =>
    setView((current) =>
      current
        ? {
            ...current,
            organizations: current.organizations.map((o) => (o.id === organization.id ? organization : o)),
          }
        : current,
    );

  const toggle = (id: string) =>
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  if (error) {
    return (
      <p className="modules-sets-note" role="alert">
        {error}
      </p>
    );
  }
  if (!view || !catalog) return <p className="modules-sets-note">Loading…</p>;
  if (view.organizations.length === 0) {
    return <p className="modules-sets-note">There is no organization whose modules you may see.</p>;
  }

  return (
    <div className="modules-sets-list">
      {view.organizations.map((organization) => {
        const expanded = open.has(organization.id);
        return (
          <section key={organization.id} className="modules-sets-org">
            <button
              type="button"
              className="modules-sets-org-header"
              onClick={() => toggle(organization.id)}
              aria-expanded={expanded}
            >
              {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              <span className="modules-sets-org-name">{organization.name}</span>
              <span className="modules-sets-org-meta">
                Modules: {partSummary(organization.set, 'modules', catalog)} · Features:{' '}
                {partSummary(organization.set, 'features', catalog)} ·{' '}
                {plural(organization.workspaces.length, 'workspace')}
              </span>
              {!organization.editable && <span className="modules-sets-org-tag">Read only</span>}
            </button>
            {expanded && (
              <div className="modules-sets-org-body">
                <SetsMatrix api={api} catalog={catalog} organization={organization} onChange={replace} />
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

/** Platform Settings › Modules & features: the sets of every organization and workspace. */
export default function PlatformModulesPage() {
  const api = useMemo(() => createIamAdminApi(), []);
  const [nonce, setNonce] = useState(0);
  return (
    <SystemFrame
      title="Modules & features"
      subtitle="The module scopes and features each organization and workspace may use. A set bounds every Allow there."
      actions={<SystemRefresh onClick={() => setNonce((n) => n + 1)} />}
    >
      <ModulesSetsView api={api} nonce={nonce} />
    </SystemFrame>
  );
}
