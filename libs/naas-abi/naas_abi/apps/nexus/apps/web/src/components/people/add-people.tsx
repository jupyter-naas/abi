'use client';

import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { AlertCircle, Search, UserPlus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input, Select } from '@/components/ui/input';
import { SettingsNotice } from '@/components/settings/settings-ui';
import { InvitePolicyPicker } from '@/components/invitations/invite-policy-picker';
import { ROLE_LABELS } from '@/components/access/roles/role-change';
import { getApiUrl } from '@/lib/config';
import type { IamAdminApi } from '@/lib/iam-admin/api';
import { cn } from '@/lib/utils';
import {
  CANDIDATE_DELAY_MS,
  CANDIDATE_MIN_CHARS,
  candidateLabel,
  candidateQuery,
  createPeopleApi,
  createUserHref,
  type MemberCandidate,
  type PeopleApi,
  type WorkspaceRole,
} from '@/lib/people';
import { InvitedBadge } from './member-status';
import { addPeopleListing, addableRoles, moveActive, optionText, type AddPeopleOption, type FoundPeople } from './add-people-model';

function avatarUrl(avatar: string | null | undefined): string {
  if (!avatar) return '';
  return avatar.startsWith('/') ? `${getApiUrl()}${avatar}` : avatar;
}

function Avatar({ name, avatar }: { name: string; avatar?: string | null }) {
  const src = avatarUrl(avatar);
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt="" className="h-8 w-8 shrink-0 object-cover" />;
  }
  return (
    <span
      aria-hidden
      className="flex h-8 w-8 shrink-0 items-center justify-center bg-primary text-sm text-primary-foreground"
    >
      {(name || '?').charAt(0).toUpperCase()}
    </span>
  );
}

const NO_MEMBERS: ReadonlySet<string> = new Set();

/**
 * Add people (Workspace settings › Members): a search box over the workspace's organization.
 * It asks from two characters on, once the typing stops; a suggestion shows avatar, name and
 * email. Picking one asks for the role (and optional policies), then adds them at once. With no
 * match, "Create user '<text>'" opens the create page prefilled. The listbox follows the
 * WAI-ARIA combobox pattern: arrows, Home and End move, Enter picks, Escape closes.
 */
export function AddPeople({
  workspaceId,
  callerRole,
  policyScope,
  memberIds = NO_MEMBERS,
  onAdded,
  navigate,
  api,
  policyApi,
  searchDelayMs = CANDIDATE_DELAY_MS,
}: {
  workspaceId: string;
  /** The caller's role here: only an owner may give owner. */
  callerRole: string | null | undefined;
  /** The workspace's IAM scope the policies attach at; null asks for none. */
  policyScope: string | null;
  /** Members already here: never suggested, even when the API still lists them. */
  memberIds?: ReadonlySet<string>;
  onAdded: (candidate: MemberCandidate, emailSent: boolean) => void | Promise<void>;
  /** Opens the create page (the router's push). */
  navigate: (href: string) => void;
  /** Tests pass fakes. */
  api?: Pick<PeopleApi, 'candidates' | 'addMember'>;
  policyApi?: Pick<IamAdminApi, 'attachable'>;
  searchDelayMs?: number;
}) {
  const client = useMemo(() => api ?? createPeopleApi(), [api]);
  const id = useId();
  const listId = `${id}-listbox`;
  const optionId = (index: number) => `${id}-option-${index}`;
  const inputRef = useRef<HTMLInputElement>(null);
  const refocus = useRef(false);

  const [text, setText] = useState('');
  const [found, setFound] = useState<FoundPeople>({ text: '', items: [] });
  const [searchError, setSearchError] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [picked, setPicked] = useState<MemberCandidate | null>(null);
  const [role, setRole] = useState<WorkspaceRole>('member');
  const [policyIds, setPolicyIds] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');

  const query = candidateQuery(text);
  useEffect(() => {
    if (!query) {
      setFound({ text: '', items: [] });
      setSearchError('');
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      client
        .candidates(workspaceId, query, controller.signal)
        .then((items) => {
          if (controller.signal.aborted) return;
          setFound({ text: query, items });
          setSearchError('');
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) return;
          setFound({ text: query, items: [] });
          setSearchError(error instanceof Error ? error.message : 'Failed to search people');
        });
    }, searchDelayMs);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [client, workspaceId, query, searchDelayMs]);

  const listing = addPeopleListing(text, found, memberIds);
  const options = listing.options;
  const expanded = open && query !== null && !picked;
  const activeIndex = active < options.length ? active : -1;

  const choose = (option: AddPeopleOption) => {
    setOpen(false);
    setActive(-1);
    if (option.kind === 'create') {
      navigate(createUserHref(workspaceId, option.text));
      return;
    }
    setPicked(option.candidate);
    setRole('member');
    setPolicyIds([]);
    setAddError('');
  };

  const reset = () => {
    setPicked(null);
    setText('');
    setPolicyIds([]);
    setRole('member');
    setAddError('');
    setFound({ text: '', items: [] });
    refocus.current = true;
  };

  // Back in the box once the pick is done (it is disabled while a pick is open).
  useEffect(() => {
    if (!picked && refocus.current) {
      refocus.current = false;
      inputRef.current?.focus();
    }
  }, [picked]);

  const add = async () => {
    if (!picked) return;
    setAdding(true);
    setAddError('');
    try {
      const { emailSent } = await client.addMember(workspaceId, { userId: picked.user_id, role, policyIds });
      await onAdded(picked, emailSent);
      reset();
    } catch (error) {
      setAddError(error instanceof Error ? error.message : 'Failed to add the member');
    } finally {
      setAdding(false);
    }
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      if (expanded) {
        event.preventDefault();
        setOpen(false);
        setActive(-1);
      } else if (text) {
        event.preventDefault();
        setText('');
      }
      return;
    }
    if (event.key === 'Enter') {
      if (expanded && activeIndex >= 0) {
        event.preventDefault();
        choose(options[activeIndex]);
      }
      return;
    }
    if (['ArrowDown', 'ArrowUp'].includes(event.key) || (expanded && ['Home', 'End'].includes(event.key))) {
      event.preventDefault();
      setOpen(true);
      setActive((current) => moveActive(current, event.key, options.length));
    }
  };

  const roles = addableRoles(callerRole);

  return (
    <div className="space-y-3" data-add-people>
      <div className="relative">
        <label htmlFor={`${id}-input`} className="sr-only">
          Add people
        </label>
        <Search
          size={14}
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          ref={inputRef}
          id={`${id}-input`}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={expanded}
          aria-controls={expanded ? listId : undefined}
          aria-activedescendant={expanded && activeIndex >= 0 ? optionId(activeIndex) : undefined}
          autoComplete="off"
          value={text}
          disabled={!!picked}
          onChange={(event) => {
            setText(event.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          placeholder={`Search the organization by name or email (${CANDIDATE_MIN_CHARS}+ characters)`}
          className="pl-9"
        />
        {expanded && (
          <ul
            id={listId}
            role="listbox"
            aria-label="People"
            className="absolute left-0 right-0 top-full z-20 mt-1 max-h-80 overflow-auto border border-border bg-popover text-popover-foreground shadow-md"
          >
            {!listing.ready ? (
              <li role="presentation" className="px-3 py-2 text-xs text-muted-foreground">
                Searching…
              </li>
            ) : (
              options.map((option, index) => (
                <li
                  key={option.key}
                  id={optionId(index)}
                  role="option"
                  aria-selected={index === activeIndex}
                  data-option={option.kind}
                  // Keeps the focus in the box: the click picks, the blur does not close first.
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => choose(option)}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 px-3 py-2 text-sm',
                    index === activeIndex ? 'bg-accent text-accent-foreground' : 'hover:bg-muted'
                  )}
                >
                  {option.kind === 'candidate' ? (
                    <>
                      <Avatar name={candidateLabel(option.candidate)} avatar={option.candidate.avatar} />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-2 truncate font-medium">
                          {candidateLabel(option.candidate)}
                          <InvitedBadge status={option.candidate.status} />
                        </span>
                        <span className="block truncate text-xs text-muted-foreground">{option.candidate.email}</span>
                      </span>
                    </>
                  ) : (
                    <>
                      <span
                        aria-hidden
                        className="flex h-8 w-8 shrink-0 items-center justify-center border border-dashed border-border text-muted-foreground"
                      >
                        <UserPlus size={14} />
                      </span>
                      <span className="min-w-0 flex-1 truncate">{optionText(option)}</span>
                    </>
                  )}
                </li>
              ))
            )}
            {listing.ready && listing.excluded > 0 && (
              <li role="presentation" className="border-t border-border px-3 py-2 text-xs text-muted-foreground" data-excluded>
                {listing.excluded === 1
                  ? '1 match is already a member here.'
                  : `${listing.excluded} matches are already members here.`}
              </li>
            )}
          </ul>
        )}
      </div>
      {searchError && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          {searchError}
        </SettingsNotice>
      )}
      <p className="text-xs text-muted-foreground">
        Suggests people of this workspace&apos;s organization who are not members here yet. Someone
        else is added with Create user and their exact email.
      </p>

      {picked && (
        <div className="space-y-3 border border-border bg-card p-3" data-add-people-pick>
          {addError && (
            <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
              {addError}
            </SettingsNotice>
          )}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <Avatar name={candidateLabel(picked)} avatar={picked.avatar} />
              <div className="min-w-0">
                <p className="flex items-center gap-2 truncate text-sm font-medium">
                  {candidateLabel(picked)}
                  <InvitedBadge status={picked.status} />
                </p>
                <p className="truncate text-xs text-muted-foreground">{picked.email}</p>
              </div>
            </div>
            <Select
              value={role}
              onChange={(event) => setRole(event.target.value as WorkspaceRole)}
              className="sm:w-40"
              aria-label="Role in this workspace"
              data-field="role"
            >
              {roles.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </Select>
            <div className="flex gap-2">
              <Button onClick={() => void add()} disabled={adding} data-action="add">
                {adding ? 'Adding…' : 'Add'}
              </Button>
              <Button variant="secondary" onClick={reset} disabled={adding}>
                Cancel
              </Button>
            </div>
          </div>
          <InvitePolicyPicker
            className="max-w-xl"
            scope={policyScope}
            value={policyIds}
            onChange={setPolicyIds}
            disabled={adding}
            api={policyApi}
          />
          <p className="text-xs text-muted-foreground">
            Added at once, and emailed that they have access.
          </p>
        </div>
      )}
    </div>
  );
}
