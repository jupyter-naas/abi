'use client';

import { useEffect, useMemo, useState } from 'react';
import { Save } from 'lucide-react';
import { featureLabel, sortFeaturesByName } from '@/lib/feature-labels';
import type { AccessViewProps } from '../access-props';
import { ROLE_LABELS } from './role-change';
import {
  MATRIX_ORDER,
  READ_ONLY_ROLE,
  baselineOf,
  changed,
  createRoleFeaturesApi,
  featuresOf,
  toggled,
  type Baseline,
  type RoleFeaturesApi,
} from './role-features-model';
import './roles.css';

type Props = AccessViewProps & { roleFeatures?: RoleFeaturesApi };

/**
 * The built-in roles of the organization and the Nexus features each gets by default: the
 * feature policies IAM attaches beside each role (`builtin.features.<org>.<role>`). Who may
 * edit them is IAM's `nexus:UpdateRoleFeatures` at the organization.
 */
export function RoleFeaturesView({ can, scope, nonce = 0, roleFeatures }: Props) {
  const client = useMemo(() => roleFeatures ?? createRoleFeaturesApi(), [roleFeatures]);
  const org = scope.organizationId;
  const [features, setFeatures] = useState<string[] | null>(null);
  const [roles, setRoles] = useState(MATRIX_ORDER);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [saved, setSaved] = useState<Baseline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState('');
  const editable = can('nexus:UpdateRoleFeatures');

  useEffect(() => {
    if (!org) return;
    let cancelled = false;
    client
      .read(org)
      .then((view) => {
        if (cancelled) return;
        setFeatures(sortFeaturesByName(featuresOf(view)));
        setRoles(MATRIX_ORDER.filter((r) => view.roles.includes(r)));
        setBaseline(baselineOf(view));
        setSaved(baselineOf(view));
        setError(null);
      })
      .catch((e: unknown) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, [client, org, nonce]);

  if (!org) return null;
  if (!features || !baseline || !saved) {
    return error ? <p className="access-source-note" role="alert">{error}</p> : <p className="access-empty">Loading…</p>;
  }

  const dirty = changed(baseline, saved);
  const query = filter.trim().toLowerCase();
  const shown = features.filter((f) => !query || `${featureLabel(f)} ${f}`.toLowerCase().includes(query));

  const save = async () => {
    setBusy(true);
    try {
      const view = await client.save(org, baseline, roles);
      setBaseline(baselineOf(view));
      setSaved(baselineOf(view));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="access-roles">
      <p className="access-empty">
        The Nexus features each built-in role gets in this organization&apos;s workspaces, within each
        workspace&apos;s set. The owner&apos;s are the deployment&apos;s.
      </p>
      <div className="access-roles-toolbar">
        <input
          type="search"
          className="access-input access-input-grow"
          aria-label="Filter features"
          placeholder="Filter features"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        {editable && (
          <button type="button" className="access-button access-button-primary" disabled={!dirty || busy} onClick={() => void save()}>
            <Save size={14} /> {busy ? 'Saving…' : 'Save changes'}
          </button>
        )}
      </div>
      {error && <p className="access-source-note" role="alert">{error}</p>}
      <div className="access-table-wrap">
        <table className="access-table">
          <thead>
            <tr>
              <th>Feature</th>
              {roles.map((role) => (
                <th key={role} className="access-roles-col" title={role === READ_ONLY_ROLE ? 'Owner access cannot be changed' : undefined}>
                  {ROLE_LABELS[role]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((feature) => (
              <tr key={feature} className="access-table-row" data-feature={feature}>
                <td>{featureLabel(feature)}</td>
                {roles.map((role) => (
                  <td key={role} className="access-roles-col">
                    <input
                      type="checkbox"
                      aria-label={`${ROLE_LABELS[role]} can use ${featureLabel(feature)}`}
                      checked={baseline[role].includes(feature)}
                      disabled={!editable || role === READ_ONLY_ROLE}
                      onChange={() => setBaseline(toggled(baseline, role, feature, features))}
                    />
                  </td>
                ))}
              </tr>
            ))}
            {shown.length === 0 && (
              <tr>
                <td colSpan={roles.length + 1} className="access-empty">No feature matches.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
