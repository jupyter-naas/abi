'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Plus, Trash2, XCircle, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import {
  SettingsNotice,
  SettingsPageHeader,
  SettingsFilterSelect,
  SettingsTableToolbar,
  countLabel,
  settingsTable,
} from '@/components/settings/settings-ui';
import { canModifySkill, useSkillsStore, type SkillScope } from '@/stores/skills';
import { useAuthStore } from '@/stores/auth';

const SCOPE_LABELS: Record<SkillScope, string> = {
  user: 'Private',
  workspace: 'Workspace',
  organization: 'Organization',
  builtin: 'Module',
};

export default function SkillsSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const workspaceId = params.workspaceId as string;
  const newSkillHref = `/workspace/${workspaceId}/settings/skills/new`;

  const { skillsByWorkspace, fetchSkills, updateSkill, deleteSkill } = useSkillsStore();
  const currentUserId = useAuthStore((s) => s.user?.id);

  const [searchQuery, setSearchQuery] = useState('');
  const [scopeFilter, setScopeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [actionError, setActionError] = useState<string | null>(null);
  const { confirm: confirmDelete, dialog: confirmDialog } = useConfirm();

  useEffect(() => {
    if (workspaceId && searchParams.get('create') === '1') {
      router.replace(newSkillHref);
    }
  }, [workspaceId, searchParams, router, newSkillHref]);

  useEffect(() => {
    if (workspaceId) void fetchSkills(workspaceId, true);
  }, [workspaceId, fetchSkills]);

  const skills = useMemo(
    () => skillsByWorkspace[workspaceId] ?? [],
    [skillsByWorkspace, workspaceId]
  );

  const filteredSkills = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return skills.filter((s) => {
      if (scopeFilter !== 'all' && s.scope !== scopeFilter) return false;
      if (statusFilter === 'enabled' && !s.enabled) return false;
      if (statusFilter === 'disabled' && s.enabled) return false;
      return (
        !q ||
        s.name.toLowerCase().includes(q) ||
        s.slug.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q)
      );
    });
  }, [skills, searchQuery, scopeFilter, statusFilter]);
  const enabledCount = skills.filter((s) => s.enabled).length;

  const handleToggleEnabled = async (id: string, enabled: boolean) => {
    setActionError(null);
    try {
      await updateSkill(id, { enabled });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update skill');
    }
  };

  const handleDelete = async (id: string, slug: string) => {
    const ok = await confirmDelete({ title: `Delete skill "/${slug}"?`, confirmLabel: 'Delete' });
    if (!ok) return;
    setActionError(null);
    try {
      await deleteSkill(id);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete skill');
    }
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Skills"
        badge={`${enabledCount} enabled`}
        description="Reusable prompts you invoke in chat with /<slug>. Module skills are enabled through workspace configuration and stay read-only."
        actions={
          <Button onClick={() => router.push(newSkillHref)}>
            <Plus size={16} />
            Add Skill
          </Button>
        }
      />

      {actionError && (
        <SettingsNotice tone="error" icon={<XCircle size={14} />}>
          {actionError}
        </SettingsNotice>
      )}

      <SettingsTableToolbar
        search={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search skills..."
        filters={
          <>
            <SettingsFilterSelect
              label="Visibility"
              value={scopeFilter}
              onChange={setScopeFilter}
              options={[
                { value: 'all', label: 'All visibilities' },
                ...(Object.keys(SCOPE_LABELS) as SkillScope[]).map((scope) => ({
                  value: scope,
                  label: SCOPE_LABELS[scope],
                })),
              ]}
            />
            <SettingsFilterSelect
              label="Status"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'All statuses' },
                { value: 'enabled', label: 'Enabled' },
                { value: 'disabled', label: 'Disabled' },
              ]}
            />
          </>
        }
        meta={`${countLabel(filteredSkills.length, skills.length, 'skill')} · ${enabledCount} enabled`}
      />

      <div className={settingsTable.wrapper}>
        <table className={settingsTable.table}>
          <thead>
            <tr className={settingsTable.headRow}>
              <th className={settingsTable.th}>Skill</th>
              <th className={settingsTable.th}>Command</th>
              <th className={settingsTable.th}>Visibility</th>
              <th className={settingsTable.th}>Last used</th>
              <th className={cn(settingsTable.th, 'w-24')}>Enabled</th>
              <th className={cn(settingsTable.th, 'w-24')}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredSkills.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-muted-foreground">
                  {skills.length > 0 ? (
                    'No skills match the current search and filters'
                  ) : (
                    <>
                      No skills yet.{' '}
                      <button
                        type="button"
                        onClick={() => router.push(newSkillHref)}
                        className="text-primary underline-offset-4 hover:underline"
                      >
                        Add Skill
                      </button>{' '}
                      to create one.
                    </>
                  )}
                </td>
              </tr>
            ) : (
              filteredSkills.map((skill) => {
                const canModify = canModifySkill(skill, currentUserId);
                return (
                  <tr
                    key={skill.id}
                    onClick={() => router.push(`/workspace/${workspaceId}/settings/skills/${skill.id}`)}
                    className={cn(settingsTable.row, 'cursor-pointer')}
                  >
                    <td className={settingsTable.td}>
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center bg-muted">
                          <Zap size={16} className="text-muted-foreground" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium">{skill.name}</p>
                          {skill.description && (
                            <p className="truncate text-xs text-muted-foreground">{skill.description}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className={cn(settingsTable.td, 'font-mono text-primary')}>/{skill.slug}</td>
                    <td className={settingsTable.td}>
                      <Badge variant="outline">{SCOPE_LABELS[skill.scope]}</Badge>
                    </td>
                    <td className={cn(settingsTable.td, 'text-muted-foreground')}>
                      {skill.lastUsedAt ? new Date(skill.lastUsedAt).toLocaleDateString() : 'Never'}
                    </td>
                    <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={skill.enabled}
                        onCheckedChange={(checked) => handleToggleEnabled(skill.id, checked)}
                        disabled={!canModify}
                        aria-label={skill.builtin ? 'Module skill is enabled in workspace configuration' : skill.enabled ? 'Disable' : 'Enable'}
                        title={skill.builtin ? 'Module skill is enabled in workspace configuration' : skill.enabled ? 'Disable' : 'Enable'}
                      />
                    </td>
                    <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
                      {canModify && (
                        <Button
                          variant="destructive-ghost"
                          size="icon"
                          onClick={() => handleDelete(skill.id, skill.slug)}
                          title="Delete"
                        >
                          <Trash2 size={14} />
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {confirmDialog}
    </div>
  );
}
