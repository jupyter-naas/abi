'use client';

import { useCallback, useEffect, useState } from 'react';
import { IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { CapabilityView } from '@/lib/iam-admin/types';
import { CAPABILITY_GROUPS, LEVEL_POLICIES } from '@/lib/access-model/levels';
import type { AccessScope } from '../access-scope';
import './groups.css';

const message = (e: unknown) => (e instanceof IamAdminError || e instanceof Error ? e.message : String(e));

/**
 * Above a level's groups, how access is made of them (ADR `20261120_access_levels_and_groups`):
 * the levels, each a generic policy written once and held by its group (read-only, in plain
 * words), and the capability groups that add one thing to a level, made on demand
 * (`GET`/`POST /api/iam/admin/capabilities`). A capability group the caller may not list here
 * is left out.
 */
export function AccessModelPanel({
  api,
  scope,
  nonce = 0,
  onOpenGroup,
  onChanged,
}: {
  api: IamAdminApi;
  scope: AccessScope;
  nonce?: number;
  onOpenGroup?: (id: string) => void;
  /** Told when a capability group was made (the list shows it). */
  onChanged?: () => void;
}) {
  const [capabilities, setCapabilities] = useState<CapabilityView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setCapabilities((await api.capabilities(scope.value)).capabilities);
    } catch {
      // Not listed here (or an older API): the levels are still shown.
      setCapabilities([]);
    }
  }, [api, scope]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const make = async (capability: CapabilityView) => {
    setBusy(capability.capability);
    try {
      await api.ensureCapability(capability.capability, scope.value);
      setError(null);
      await load();
      onChanged?.();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="access-model-panel" aria-label="How access is given">
      <div className="access-model-block" data-access-levels="">
        <h3 className="access-group-heading">Levels</h3>
        <p className="access-group-hint">
          A person has one level wherever they work; the workspace groups say where. Each level is a generic
          policy, written once and held by its group, read-only.
        </p>
        <ul className="access-model-list">
          {LEVEL_POLICIES.map((level) => (
            <li key={level.level} className="access-model-item" data-level={level.level}>
              <span className="access-model-name">
                {level.name} <span className="access-model-via">· held by {level.group}</span>
              </span>
              <span className="access-group-hint">{level.summary}</span>
            </li>
          ))}
        </ul>
      </div>
      {capabilities && capabilities.length > 0 && (
        <div className="access-model-block" data-capabilities="">
          <h3 className="access-group-heading">Capability groups</h3>
          <p className="access-group-hint">Each adds one thing to a level, for the people put in it.</p>
          {error && (
            <p className="access-policy-error" role="alert">
              {error}
            </p>
          )}
          <ul className="access-model-list">
            {capabilities.map((capability) => {
              const known = CAPABILITY_GROUPS.find((c) => c.capability === capability.capability);
              return (
                <li key={capability.capability} className="access-model-item" data-capability={capability.capability}>
                  <span className="access-model-name">
                    {capability.group_id && onOpenGroup ? (
                      <button type="button" className="access-holding-link" onClick={() => onOpenGroup(capability.group_id!)}>
                        {capability.name}
                      </button>
                    ) : (
                      capability.name
                    )}
                    {!capability.group_id && (
                      <span className="access-model-via"> · not made yet</span>
                    )}
                  </span>
                  {known && <span className="access-group-hint">{known.summary}</span>}
                  {!capability.group_id && capability.can_create && (
                    <button
                      type="button"
                      className="platform-users-button"
                      data-action="create-capability"
                      disabled={busy === capability.capability}
                      onClick={() => void make(capability)}
                    >
                      {busy === capability.capability ? 'Creating…' : `Create ${capability.name}`}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
