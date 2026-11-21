'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { createIamAdminApi, IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { CapabilityView, PolicyView } from '@/lib/iam-admin/types';
import { modelSets } from '@/lib/access-model/model-sets';
import { platformAccessPath } from '@/components/access/access-paths';
import '@/components/access/access-base.css';
import '@/components/access/groups/groups.css';
import './model-sets.css';

/** How many pages of platform policies are read to find the sets. */
const MAX_PAGES = 10;

const message = (e: unknown) => (e instanceof IamAdminError || e instanceof Error ? e.message : String(e));

/**
 * Platform settings › Models › Sets (S3, #1586): the members' default set
 * (`nexus_config.models.member_set`), every model, and the embedding models, each a platform
 * policy kept in step with the configuration at each start; read-only here (the configuration is
 * where a set changes). "Models · all" is also a capability group, made on demand.
 */
export function ModelSets({ api, nonce = 0 }: { api?: IamAdminApi; nonce?: number }) {
  const client = useMemo(() => api ?? createIamAdminApi(), [api]);
  const [policies, setPolicies] = useState<PolicyView[] | null>(null);
  const [group, setGroup] = useState<CapabilityView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const found: PolicyView[] = [];
      let after: string | undefined;
      for (let page = 0; page < MAX_PAGES; page += 1) {
        const read = await client.listPolicies(after);
        found.push(...read.items);
        if (!read.next_after || modelSets(found).every((s) => s.policy)) break;
        after = read.next_after;
      }
      setPolicies(found);
      setError(null);
    } catch (e) {
      setError(message(e));
    }
    try {
      const capabilities = (await client.capabilities(null)).capabilities;
      setGroup(capabilities.find((c) => c.capability === 'models_all') ?? null);
    } catch {
      setGroup(null);
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const make = async () => {
    setBusy(true);
    try {
      setGroup(await client.ensureCapability('models_all', null));
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };

  if (error && !policies) return <p className="access-source-note" role="alert">{error}</p>;
  if (!policies) return <p className="access-empty">Loading…</p>;

  const sets = modelSets(policies);
  return (
    <section className="model-sets" aria-label="Sets" data-model-sets="">
      <h2 className="model-sets-title">Sets</h2>
      <p className="access-group-hint">
        A Viewer chats with no model, a Member with the members&apos; default set, an admin with every model; every
        Member and Viewer embeds (search). Sets come from the configuration and are kept in step at each start:
        read-only here.
      </p>
      {error && <p className="access-policy-error" role="alert">{error}</p>}
      <div className="model-sets-grid">
        {sets.map((set) => (
          <article key={set.key} className="access-model-block" data-model-set={set.key}>
            <h3 className="access-group-heading">{set.title}</h3>
            <p className="access-group-hint">
              {set.policy ? (
                <a className="access-holding-link" href={platformAccessPath('policies', set.policy.id)}>
                  {set.name}
                </a>
              ) : (
                <>{set.name} · not made yet (made at the next start)</>
              )}{' '}
              · held by {set.heldBy}
            </p>
            {set.key === 'member' && (
              <p className="access-group-hint">
                From <code>nexus_config.models.member_set</code>.
              </p>
            )}
            {set.models === 'all' ? (
              <p className="model-sets-all">Every model</p>
            ) : set.models.length === 0 ? (
              <p className="access-group-hint" data-model-set-empty="">
                {set.key === 'member'
                  ? 'Empty: Members chat with no model directly (their agents still use their own).'
                  : 'No model.'}
              </p>
            ) : (
              <ul className="model-sets-models">
                {set.models.map((id) => (
                  <li key={id}>
                    <code>{id}</code>
                  </li>
                ))}
              </ul>
            )}
            {set.key === 'all' && group && (
              <div className="model-sets-group" data-capability="models_all">
                {group.group_id ? (
                  <a className="access-holding-link" href={platformAccessPath('groups', group.group_id)}>
                    Group {group.name}
                  </a>
                ) : group.can_create ? (
                  <button
                    type="button"
                    className="platform-users-button"
                    data-action="create-capability"
                    disabled={busy}
                    onClick={() => void make()}
                  >
                    {busy ? 'Creating…' : `Create the group ${group.name}`}
                  </button>
                ) : (
                  <span className="access-group-hint">The group {group.name} is not made yet.</span>
                )}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
