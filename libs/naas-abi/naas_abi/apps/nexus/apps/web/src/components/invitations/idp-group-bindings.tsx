'use client';

import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input, Select } from '@/components/ui/input';
import { SettingsNotice, SettingsSection, settingsTable } from '@/components/settings/settings-ui';
import {
  bindGroup,
  fetchGroupBindings,
  unbindGroup,
  type GroupBinding,
  type GroupBindings,
  type InviteScope,
} from '@/lib/invitations';

const label = (role: string) => role.charAt(0).toUpperCase() + role.slice(1);

/**
 * The identity provider's groups that hold a role here: the members of the
 * group get the role the next time they sign in. Hidden when no provider is
 * configured, and for anyone who cannot manage the scope.
 */
export function IdpGroupBindings({
  scope,
  id,
  canManage,
}: {
  scope: InviteScope;
  id: string;
  canManage: boolean;
}) {
  const [state, setState] = useState<GroupBindings | null>(null);
  const [error, setError] = useState('');
  const [provider, setProvider] = useState('');
  const [group, setGroup] = useState('');
  const [role, setRole] = useState('');
  const [busy, setBusy] = useState(false);

  const apply = useCallback((next: GroupBindings) => {
    setState(next);
    setProvider((current) =>
      next.providers.some((p) => p.name === current) ? current : (next.providers[0]?.name ?? '')
    );
    setRole((current) => (next.roles.includes(current) ? current : (next.roles[0] ?? '')));
  }, []);

  useEffect(() => {
    if (!canManage || !id) return;
    let cancelled = false;
    fetchGroupBindings(scope, id)
      .then((next) => {
        if (!cancelled) apply(next);
      })
      .catch((failure) => {
        if (!cancelled) setError(failure instanceof Error ? failure.message : 'Failed to load groups');
      });
    return () => {
      cancelled = true;
    };
  }, [canManage, id, scope, apply]);

  if (!canManage || !state || state.providers.length === 0) return null;

  const run = async (work: () => Promise<GroupBindings>) => {
    setBusy(true);
    setError('');
    try {
      apply(await work());
      return true;
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The change failed');
      return false;
    } finally {
      setBusy(false);
    }
  };

  const add = async () => {
    if (!provider || !group.trim() || !role) return;
    const binding: GroupBinding = { provider, group: group.trim(), role };
    if (await run(() => bindGroup(scope, id, binding))) setGroup('');
  };

  return (
    <SettingsSection
      title="Identity provider groups"
      description="Everyone in a group of your identity provider gets the role here when they sign in. Group names are the ones the provider sends."
    >
      {error && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />} className="mb-4">
          {error}
        </SettingsNotice>
      )}
      {state.bindings.length > 0 && (
        <div className={`${settingsTable.wrapper} mb-4`}>
          <table className={settingsTable.table}>
            <thead>
              <tr className={settingsTable.headRow}>
                <th className={settingsTable.th}>Provider</th>
                <th className={settingsTable.th}>Group</th>
                <th className={settingsTable.th}>Role</th>
                <th className={`${settingsTable.th} text-right`}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {state.bindings.map((binding) => (
                <tr key={`${binding.provider}/${binding.group}/${binding.role}`} className={settingsTable.row}>
                  <td className={settingsTable.td}>
                    {state.providers.find((p) => p.name === binding.provider)?.display_name ??
                      binding.provider}
                  </td>
                  <td className={settingsTable.td}>{binding.group}</td>
                  <td className={settingsTable.td}>{label(binding.role)}</td>
                  <td className={`${settingsTable.td} text-right`}>
                    <Button
                      variant="destructive-ghost"
                      size="icon"
                      title="Remove this binding"
                      disabled={busy}
                      onClick={() => void run(() => unbindGroup(scope, id, binding))}
                    >
                      <Trash2 size={14} />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex flex-col gap-3 sm:flex-row">
        {state.providers.length > 1 && (
          <Select
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
            className="sm:w-48"
            aria-label="Identity provider"
          >
            {state.providers.map((p) => (
              <option key={p.name} value={p.name}>
                {p.display_name}
              </option>
            ))}
          </Select>
        )}
        <Input
          value={group}
          onChange={(event) => setGroup(event.target.value)}
          placeholder="Group name, e.g. data-team"
          className="flex-1"
          aria-label="Group name"
        />
        <Select
          value={role}
          onChange={(event) => setRole(event.target.value)}
          className="sm:w-40"
          aria-label="Role"
        >
          {state.roles.map((r) => (
            <option key={r} value={r}>
              {label(r)}
            </option>
          ))}
        </Select>
        <Button onClick={() => void add()} disabled={busy || !group.trim()}>
          Bind group
        </Button>
      </div>
    </SettingsSection>
  );
}
