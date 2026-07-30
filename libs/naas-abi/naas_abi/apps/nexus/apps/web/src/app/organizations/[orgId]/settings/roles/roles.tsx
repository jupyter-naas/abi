'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { AlertCircle, Save, Shield } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import '../components/org-settings-components.css';
import './roles.css';

type RoleName = 'owner' | 'admin' | 'member' | 'viewer';

type RoleFeaturesResponse = {
  enabled_features: string[];
  role_baseline: Record<string, string[]>;
  known_features: string[];
  roles: RoleName[];
  persistence?: 'database' | 'deployment' | string;
  note?: string;
};

const ROLE_LABELS: Record<RoleName, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
  viewer: 'Viewer',
};

const FEATURE_LABELS: Record<string, string> = {
  maps: 'Maps',
  chat: 'Chat',
  files: 'Files',
  agents: 'Agents',
  skills: 'Skills',
  apps: 'Apps',
  marketplace: 'Marketplace',
  search: 'Search',
  ontology: 'Ontology',
  graph: 'Graph',
  settings: 'Settings',
  code: 'Code',
  slides: 'Slides',
};

function emptyBaseline(roles: RoleName[]): Record<RoleName, string[]> {
  return {
    owner: [],
    admin: [],
    member: [],
    viewer: [],
    ...Object.fromEntries(roles.map((role) => [role, []])),
  } as Record<RoleName, string[]>;
}

export default function OrgRolesPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  const authUser = useAuthStore((s) => s.user);
  const { fetchMembers, membersCache } = useOrganizationStore();
  const members = membersCache[orgId] || [];
  const myMembership = members.find((m) => m.userId === authUser?.id);
  const canManage =
    myMembership?.role === 'owner' || myMembership?.role === 'admin';

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [persistence, setPersistence] = useState('deployment');
  const [features, setFeatures] = useState<string[]>([]);
  const [roles, setRoles] = useState<RoleName[]>([
    'owner',
    'admin',
    'member',
    'viewer',
  ]);
  const [baseline, setBaseline] = useState<Record<RoleName, string[]>>(
    emptyBaseline(['owner', 'admin', 'member', 'viewer'])
  );
  const [initialBaseline, setInitialBaseline] = useState<
    Record<RoleName, string[]>
  >(emptyBaseline(['owner', 'admin', 'member', 'viewer']));

  useEffect(() => {
    if (orgId) {
      void fetchMembers(orgId);
    }
  }, [orgId, fetchMembers]);

  useEffect(() => {
    const load = async () => {
      if (!orgId) return;
      setLoading(true);
      setError('');
      try {
        const { authFetch } = await import('@/stores/auth');
        const response = await authFetch(
          `/api/organizations/${orgId}/roles/features`
        );
        if (!response.ok) {
          throw new Error('Failed to load role features');
        }
        const data: RoleFeaturesResponse = await response.json();
        const nextRoles = (data.roles || [
          'owner',
          'admin',
          'member',
          'viewer',
        ]) as RoleName[];
        const nextFeatures =
          data.enabled_features?.length > 0
            ? data.enabled_features
            : data.known_features || [];
        const nextBaseline = emptyBaseline(nextRoles);
        for (const role of nextRoles) {
          nextBaseline[role] = [...(data.role_baseline?.[role] || [])];
        }
        setRoles(nextRoles);
        setFeatures(nextFeatures);
        setBaseline(nextBaseline);
        setInitialBaseline({
          owner: [...nextBaseline.owner],
          admin: [...nextBaseline.admin],
          member: [...nextBaseline.member],
          viewer: [...nextBaseline.viewer],
        });
        setPersistence(data.persistence || 'deployment');
        setNote(data.note || '');
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : 'Failed to load role features'
        );
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [orgId]);

  const dirty = useMemo(() => {
    return roles.some((role) => {
      const a = [...(baseline[role] || [])].sort().join(',');
      const b = [...(initialBaseline[role] || [])].sort().join(',');
      return a !== b;
    });
  }, [baseline, initialBaseline, roles]);

  const toggleFeature = (role: RoleName, feature: string) => {
    if (!canManage) return;
    setBaseline((current) => {
      const existing = new Set(current[role] || []);
      if (existing.has(feature)) {
        existing.delete(feature);
      } else {
        existing.add(feature);
      }
      return {
        ...current,
        [role]: features.filter((key) => existing.has(key)),
      };
    });
  };

  const handleSave = async () => {
    if (!orgId || !canManage || !dirty) return;
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(
        `/api/organizations/${orgId}/roles/features`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            role_baseline: Object.fromEntries(
              roles.map((role) => [role, baseline[role] || []])
            ),
          }),
        }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to save role features');
      }
      const data: RoleFeaturesResponse = await response.json();
      if (data.persistence !== 'database') {
        throw new Error(
          'Save did not persist to the database. Try again or contact support.'
        );
      }
      const nextBaseline = emptyBaseline(roles);
      for (const role of roles) {
        nextBaseline[role] = [...(data.role_baseline?.[role] || [])];
      }
      setBaseline(nextBaseline);
      setInitialBaseline({
        owner: [...nextBaseline.owner],
        admin: [...nextBaseline.admin],
        member: [...nextBaseline.member],
        viewer: [...nextBaseline.viewer],
      });
      setPersistence(data.persistence);
      setNote(data.note || note);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to save role features'
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="org-settings-loading">Loading roles...</div>;
  }

  const footnote =
    note ||
    (persistence === 'database'
      ? 'Role feature access for this organization is saved in the database and applies across API workers and restarts.'
      : 'Role feature access currently uses the deployment baseline from nexus_config.feature_flags. Save writes a durable organization overlay.');

  return (
    <div className="org-settings-roles-page">
      <OrgSettingsPageHeader
        title="Roles"
        subtitle="Define which workspace features each role can access"
        actions={
          canManage ? (
            <button
              type="button"
              className={
                saved
                  ? 'org-settings-primary-button org-settings-primary-button-saved'
                  : 'org-settings-primary-button'
              }
              onClick={() => void handleSave()}
              disabled={!dirty || saving}
            >
              <Save size={16} />
              {saved ? 'Saved' : saving ? 'Saving...' : 'Save'}
            </button>
          ) : undefined
        }
      />

      {error && (
        <div className="org-settings-roles-alert" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <OrgSettingsSectionCard flush overflowHidden>
        <div className="org-settings-roles-card-heading">
          <Shield size={18} />
          <div>
            <p className="org-settings-roles-card-title">Feature access matrix</p>
            <p className="org-settings-roles-card-subtitle">
              Driven by nexus_config.feature_flags (owner / admin / member /
              viewer). Custom named roles are deferred.
            </p>
          </div>
        </div>

        <div className="org-settings-roles-table-wrap">
          <table className="org-settings-roles-table">
            <thead>
              <tr>
                <th scope="col">Feature</th>
                {roles.map((role) => (
                  <th key={role} scope="col">
                    {ROLE_LABELS[role] || role}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {features.map((feature) => (
                <tr key={feature}>
                  <th scope="row">{FEATURE_LABELS[feature] || feature}</th>
                  {roles.map((role) => {
                    const checked = (baseline[role] || []).includes(feature);
                    return (
                      <td key={`${role}-${feature}`}>
                        <label className="org-settings-roles-check">
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={!canManage}
                            onChange={() => toggleFeature(role, feature)}
                            aria-label={`${ROLE_LABELS[role]} can access ${FEATURE_LABELS[feature] || feature}`}
                          />
                        </label>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </OrgSettingsSectionCard>

      <p className="org-settings-footnote">{footnote}</p>
    </div>
  );
}
