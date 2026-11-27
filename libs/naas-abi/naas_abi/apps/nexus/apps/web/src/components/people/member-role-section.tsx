'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useConfirm } from '@/components/ui/dialogs';
import {
  addable,
  createMemberRolesApi,
  heldItems,
  roleProblem,
  withRoles,
  withoutRole,
  type HeldItem,
  type HeldRoles,
  type MemberRolesApi,
  type RoleManaged,
  type RoleOption,
  type RoleOptions,
  type RoleScope,
  type RoleSelection,
} from '@/lib/member-roles';
import { RolePickerDialog, roleHint } from './role-picker-dialog';
import { Notice } from '@/components/ui/notice';
import { Card } from '@/components/ui/card';

const NOTHING: HeldRoles = { groups: [], policies: [], names: {} };

const GROUPS_HELP: Record<RoleScope['kind'], string> = {
  workspace: 'The groups they are in that bear on this workspace. A level (Members, Viewers) applies in all their workspaces.',
  organization: "The organization's groups they are in. A level (Members, Viewers) applies in all their workspaces.",
  platform: "The platform's groups they are in. A level applies in all their workspaces.",
};

const POLICIES_HELP: Record<RoleScope['kind'], string> = {
  workspace: 'The policies attached to them here.',
  organization: 'The policies attached to them in this organization.',
  platform: 'The policies attached to them everywhere (without a scope).',
};

const WORKSPACES_HELP = "The organization's workspaces they work in, and those they administer.";

type PickerKind = 'workspaces' | 'groups' | 'policies';

/** Why a group cannot be removed here, said in its place. */
const MANAGED_TEXT: Record<RoleManaged, { label: string; title: string }> = {
  admins: { label: 'Comes with their admins group', title: 'They reach it as an admin' },
  organization: { label: "Managed in the organization's Users", title: "Change it in the organization's settings › Users" },
  platform: { label: "Managed in the platform's Users", title: 'Change it in Platform settings › Users' },
};

/** A person as their page names them, once found among the people of the scope. */
export type PersonRef = { userId: string; name: string; email: string | null };

/**
 * A person's Role at a workspace, an organization or the platform, on their page (Users › a
 * person): lists of what they hold there, Groups and Policies (and first, at an organization,
 * the Workspaces its workspaces' groups place them in). Removing one asks for a
 * confirmation; the add button opens a search of the ones they may be given, one or several
 * picked. Each change is saved at once (`PUT …/roles`), what the API would refuse said before
 * asking (`roleProblem`). At a workspace the page names them by their IAM id (`principalId`):
 * they are found among its members (an organization's admin reaches it without a level).
 */
export function MemberRoleSection({
  scope,
  userId,
  principalId,
  nonce = 0,
  onChanged,
  onPerson,
  api,
  onLeave,
}: {
  scope: RoleScope;
  /** Their Nexus id (an organization's, the platform's page; the platform takes their IAM id too). */
  userId?: string;
  /** At a workspace: their IAM id, looked up among its members. */
  principalId?: string;
  /** Bumped to read it all again (the page's Refresh). */
  nonce?: number;
  onChanged?: () => void;
  /** At a workspace: the member found, so the page names them. */
  onPerson?: (person: PersonRef | null) => void;
  api?: MemberRolesApi;
  /** At a workspace: takes them out of it (the page's own route, as its Users list does).
   *  Their membership row offers it, after a confirmation; without it the row is kept. */
  onLeave?: () => Promise<void>;
}) {
  const roles = useMemo(() => api ?? createMemberRolesApi(), [api]);
  const { confirm, dialog: confirmDialog } = useConfirm();
  const [person, setPerson] = useState<(PersonRef & { reachesOtherwise: boolean }) | null | undefined>(undefined);
  const [options, setOptions] = useState<RoleOptions>({ groups: [], policies: [] });
  const [held, setHeld] = useState<HeldRoles>(NOTHING);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [picker, setPicker] = useState<PickerKind | null>(null);
  const scopeKey = scope.kind === 'platform' ? 'platform' : `${scope.kind}:${scope.id}`;

  useEffect(() => {
    let live = true;
    setError('');
    (async () => {
      let found: (PersonRef & { reachesOtherwise: boolean }) | null = null;
      if (scope.kind === 'workspace' && principalId && !userId) {
        const member = await roles.member(scope.id, principalId);
        found = member
          ? { userId: member.userId, name: member.name, email: member.email, reachesOtherwise: member.source === 'organization' }
          : null;
        if (live) onPerson?.(found);
      } else if (userId) {
        found = { userId, name: '', email: null, reachesOtherwise: scope.kind === 'platform' };
      }
      if (!live) return;
      setPerson(found);
      if (!found) return;
      const [offered, mine] = await Promise.all([roles.options(scope), roles.held(scope, found.userId)]);
      if (!live) return;
      setOptions(offered);
      setHeld(mine);
    })().catch((e: unknown) => live && setError(e instanceof Error ? e.message : 'Could not load their roles'));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `scope` is read through its key
  }, [roles, scopeKey, userId, principalId, nonce]);

  if (person === null) return null; // not one of its people: their page says the rest
  const reachesOtherwise = !!person?.reachesOtherwise;
  const items = heldItems(options, held);
  const more = addable(options, held);
  const who = person?.name || 'They';
  const ready = person !== undefined && !busy;

  const save = async (next: RoleSelection, done: string) => {
    if (!person) return;
    await roles.set(scope, person.userId, { groups: next.groups, policies: next.policies });
    setHeld(await roles.held(scope, person.userId));
    setError('');
    setNotice(done);
    onChanged?.();
  };

  // Their membership group is the workspace itself: leaving it takes them out of the
  // workspace, with their level and what is attached to them there. Asked first.
  const leave = async () => {
    if (!onLeave) return;
    const name = person?.name || person?.email || 'them';
    const ok = await confirm({
      title: `Remove ${name} from this workspace?`,
      description:
        'They leave it: its groups, their level and the policies attached to them here. Their account and their other workspaces stay.',
      confirmLabel: 'Remove from workspace',
    });
    if (!ok) return;
    setError('');
    try {
      await onLeave();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not remove them from the workspace.');
    }
  };

  const remove = async (option: RoleOption) => {
    setNotice('');
    const next = withoutRole(held, option);
    const problem = roleProblem(options, next, reachesOtherwise);
    if (problem) {
      setError(problem);
      return;
    }
    const ok = await confirm({
      title: option.kind === 'policy' ? `Detach ${option.name}?` : `Remove from ${option.name}?`,
      description:
        option.kind === 'policy'
          ? `${who} will lose what the policy ${option.name} gives them.`
          : `${who} will leave the group ${option.name} and lose what it gives them.`,
      confirmLabel: option.kind === 'policy' ? 'Detach' : 'Remove',
    });
    if (!ok) return;
    setBusy(true);
    try {
      await save(next, `${option.name} removed.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change their roles');
    } finally {
      setBusy(false);
    }
  };

  const add = async (picked: RoleOption[]) => {
    setNotice('');
    setBusy(true);
    try {
      await save(withRoles(options, held, picked), picked.length > 1 ? `${picked.length} added.` : `${picked[0]?.name} added.`);
      setPicker(null);
    } finally {
      setBusy(false);
    }
  };

  const list = (found: HeldItem[], empty: string) =>
    found.length === 0 ? (
      <p className="text-sm text-muted-foreground">{empty}</p>
    ) : (
      <ul className="divide-y divide-border">
        {found.map((option) => {
          const hint = roleHint(option);
          return (
            <li
              key={`${option.kind}:${option.id}`}
              className="flex items-center justify-between gap-3 py-2"
              data-role-item={option.id}
              data-role={option.kind}
            >
              <span className="min-w-0">
                <span className="block truncate text-sm text-foreground">{option.name}</span>
                {hint && <span className="block text-xs text-muted-foreground">{hint}</span>}
              </span>
              {option.managed ? (
                <span className="shrink-0 text-xs text-muted-foreground" title={MANAGED_TEXT[option.managed].title} data-managed={option.managed}>
                  {MANAGED_TEXT[option.managed].label}
                </span>
              ) : option.kind === 'own' && onLeave && scope.kind === 'workspace' ? (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={!ready}
                  onClick={() => void leave()}
                  data-action="remove-from-workspace"
                >
                  <Trash2 size={14} />
                  Remove from workspace
                </Button>
              ) : option.kind === 'own' ? (
                <span
                  className="shrink-0 text-xs text-muted-foreground"
                  title={
                    scope.kind === 'workspace'
                      ? 'Remove from workspace, at the top right, takes them out'
                      : 'Remove them from Users to take them out'
                  }
                >
                  Kept while they are here
                </span>
              ) : (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove ${option.name}`}
                  title={option.kind === 'policy' ? 'Detach' : 'Remove'}
                  disabled={!ready}
                  onClick={() => void remove(option)}
                  data-action="remove-role"
                >
                  <Trash2 size={15} />
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    );

  const ADD_LABEL: Record<PickerKind, string> = { workspaces: 'Add workspaces', groups: 'Add groups', policies: 'Add policies' };
  const addButton = (kind: PickerKind, offered: RoleOption[]) => (
    <Button
      variant="secondary"
      size="sm"
      onClick={() => {
        setNotice('');
        setPicker(kind);
      }}
      disabled={!ready || offered.length === 0}
      title={offered.length === 0 ? 'Nothing more you may add' : undefined}
      data-action={`add-${kind}`}
    >
      {/* A text button, as every section's "+ …" (UX-06): the icon alone said nothing. */}
      <Plus size={14} />
      {ADD_LABEL[kind]}
    </Button>
  );

  // At an organization, its workspaces' groups are a section of their own.
  const split = scope.kind === 'organization';
  const inWorkspace = (o: RoleOption) => split && !!o.workspace;
  const heldWorkspaces = items.groups.filter(inWorkspace).sort((a, b) => a.name.localeCompare(b.name));
  const heldGroups = items.groups.filter((o) => !inWorkspace(o));
  const moreWorkspaces = more.filter(inWorkspace);
  const moreGroups = more.filter((o) => o.kind !== 'policy' && !inWorkspace(o));
  const morePolicies = more.filter((o) => o.kind === 'policy');
  const offered: Record<PickerKind, RoleOption[]> = { workspaces: moreWorkspaces, groups: moreGroups, policies: morePolicies };
  const loading = <p className="text-sm text-muted-foreground">Loading…</p>;
  const problemOf = (picked: RoleOption[]) => roleProblem(options, withRoles(options, held, picked), reachesOtherwise);

  return (
    <div className="space-y-4" data-member-role="">
      {error && (
        <Notice tone="error" icon={<AlertCircle size={14} />}>
          {error}
        </Notice>
      )}
      {notice && <Notice tone="info">{notice}</Notice>}
      {split && (
        <Card title="Workspaces" description={WORKSPACES_HELP} actions={addButton('workspaces', moreWorkspaces)}>
          <div data-role-list="workspaces">{person === undefined ? loading : list(heldWorkspaces, 'In none of its workspaces.')}</div>
        </Card>
      )}
      <Card title="Groups" description={GROUPS_HELP[scope.kind]} actions={addButton('groups', moreGroups)}>
        <div data-role-list="groups">{person === undefined ? loading : list(heldGroups, 'In no group here.')}</div>
      </Card>
      <Card title="Policies" description={POLICIES_HELP[scope.kind]} actions={addButton('policies', morePolicies)}>
        <div data-role-list="policies">{person === undefined ? loading : list(items.policies, 'No policy attached to them here.')}</div>
      </Card>
      {picker && (
        <RolePickerDialog
          open
          title={ADD_LABEL[picker]}
          options={offered[picker]}
          onClose={() => setPicker(null)}
          onAdd={add}
          problemOf={problemOf}
        />
      )}
      {confirmDialog}
    </div>
  );
}
