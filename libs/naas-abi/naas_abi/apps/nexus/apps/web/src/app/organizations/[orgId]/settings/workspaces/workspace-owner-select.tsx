'use client';

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import '@/components/shell/sidebar/ontology-picker.css';

export type OrgMemberOption = {
  userId: string;
  email: string;
  name?: string;
};

function memberLabel(member: OrgMemberOption): string {
  return member.name ? `${member.name} · ${member.email}` : member.email;
}

function memberDetail(member: OrgMemberOption): string | undefined {
  return member.name ? member.email : undefined;
}

export function WorkspaceOwnerSelect({
  orgId,
  value,
  onChange,
  disabled,
}: {
  orgId: string;
  value: string;
  onChange: (userId: string) => void;
  disabled?: boolean;
}) {
  const [members, setMembers] = useState<OrgMemberOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [box, setBox] = useState<{
    top: number;
    left: number;
    width: number;
    maxHeight: number;
  } | null>(null);

  const wrapRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listId = useId();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void authFetch(`/api/organizations/${orgId}/members`)
      .then(async (res) => {
        if (!res.ok || cancelled) return;
        const rows: { user_id: string; email?: string; name?: string }[] = await res.json();
        setMembers(
          rows.map((row) => ({
            userId: row.user_id,
            email: row.email || row.user_id,
            name: row.name,
          }))
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  const options = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return members;
    return members.filter(
      (member) =>
        member.email.toLowerCase().includes(q) ||
        (member.name || '').toLowerCase().includes(q) ||
        member.userId.toLowerCase().includes(q)
    );
  }, [members, query]);

  const selected = members.find((member) => member.userId === value);
  const triggerLabel = loading
    ? 'Loading members…'
    : selected
      ? memberLabel(selected)
      : 'Select owner…';

  const optionCount = options.length;
  const active = optionCount ? Math.min(activeIndex, optionCount - 1) : 0;

  const close = useCallback((restoreFocus = false) => {
    setOpen(false);
    setQuery('');
    setActiveIndex(0);
    if (restoreFocus) triggerRef.current?.focus();
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    const anchor = wrapRef.current;
    if (!anchor) return;
    function position() {
      const rect = anchor?.getBoundingClientRect();
      if (!rect) return;
      const roomBelow = window.innerHeight - rect.bottom - 12;
      const roomAbove = rect.top - 12;
      const below = roomBelow >= 220 || roomBelow >= roomAbove;
      const maxHeight = Math.max(80, Math.min(448, below ? roomBelow : roomAbove));
      const width = Math.min(Math.max(rect.width, 280), window.innerWidth - 16);
      setBox({
        top: below ? rect.bottom + 4 : rect.top - maxHeight - 4,
        left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
        width,
        maxHeight,
      });
    }
    position();
    const observer = new ResizeObserver(position);
    observer.observe(anchor);
    window.addEventListener('resize', position);
    const onScroll = (event: Event) => {
      if (!(event.target instanceof Node) || !popupRef.current?.contains(event.target)) position();
    };
    window.addEventListener('scroll', onScroll, true);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', position);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [open]);

  const positioned = box !== null;
  useEffect(() => {
    if (!open || !positioned) return;
    searchRef.current?.focus();
  }, [open, positioned]);

  useEffect(() => {
    if (!open) return;
    const outside = (event: Event) => {
      const target = event.target as Node;
      if (!wrapRef.current?.contains(target) && !popupRef.current?.contains(target)) close();
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('focusin', outside);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('focusin', outside);
    };
  }, [open, close]);

  useEffect(() => {
    if (open) {
      popupRef.current
        ?.querySelector<HTMLElement>(`[data-option-index="${active}"]`)
        ?.scrollIntoView({ block: 'nearest' });
    }
  }, [active, open]);

  function pick(index: number) {
    const member = options[index];
    if (!member) return;
    onChange(member.userId);
    close(true);
  }

  const triggerDisabled = disabled || loading;

  return (
    <div ref={wrapRef} className="ontology-picker">
      <button
        ref={triggerRef}
        type="button"
        disabled={triggerDisabled}
        onClick={() => {
          if (triggerDisabled) return;
          if (open) close();
          else {
            setQuery('');
            setActiveIndex(0);
            setOpen(true);
          }
        }}
        className={cn(
          'ontology-picker-trigger account-profile-field-input min-h-9 justify-between text-sm text-foreground',
          value && 'is-filtered'
        )}
        aria-label={`Workspace owner: ${triggerLabel}`}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={open ? listId : undefined}
        title={triggerLabel}
      >
        <span className="ontology-picker-label">{triggerLabel}</span>
        <ChevronDown size={14} className="shrink-0 opacity-70" />
      </button>
      {open &&
        box &&
        createPortal(
          <div
            ref={popupRef}
            className="fixed z-[260] flex flex-col overflow-hidden border border-border bg-background shadow-xl"
            style={box}
          >
            <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background px-3 py-2">
              <Search size={14} className="shrink-0 text-muted-foreground opacity-70" />
              <input
                ref={searchRef}
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setActiveIndex(0);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') {
                    event.preventDefault();
                    close(true);
                  } else if (event.key === 'Tab') {
                    close(true);
                  } else if (event.key === 'ArrowDown') {
                    event.preventDefault();
                    setActiveIndex(Math.min(active + 1, Math.max(optionCount - 1, 0)));
                  } else if (event.key === 'ArrowUp') {
                    event.preventDefault();
                    setActiveIndex(Math.max(active - 1, 0));
                  } else if (event.key === 'Enter' && optionCount) {
                    event.preventDefault();
                    pick(active);
                  }
                }}
                placeholder="Search members…"
                className="min-w-0 flex-1 bg-transparent text-xs text-foreground outline-none focus-visible:ring-0 placeholder:text-muted-foreground"
                role="combobox"
                aria-label="Search organization members"
                aria-autocomplete="list"
                aria-expanded={open}
                aria-controls={listId}
                aria-activedescendant={optionCount ? `${listId}-${active}` : undefined}
              />
            </div>
            <div className="min-h-0 overflow-y-auto">
              <div id={listId} role="listbox" aria-label="Workspace owner">
                {options.map((member, index) => {
                  const checked = member.userId === value;
                  return (
                    <button
                      key={member.userId}
                      type="button"
                      role="option"
                      aria-selected={checked}
                      id={`${listId}-${index}`}
                      data-option-index={index}
                      tabIndex={-1}
                      title={memberLabel(member)}
                      onMouseEnter={() => setActiveIndex(index)}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => pick(index)}
                      className={cn(
                        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs',
                        active === index ? 'bg-muted' : 'hover:bg-muted/70'
                      )}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate">
                          {member.name || member.email}
                        </span>
                        {memberDetail(member) && (
                          <span className="block truncate text-[11px] text-muted-foreground">
                            {memberDetail(member)}
                          </span>
                        )}
                      </span>
                      {checked && <Check size={14} className="shrink-0 text-workspace-accent" />}
                    </button>
                  );
                })}
              </div>
              {!loading && !options.length && (
                <p role="status" className="px-3 py-4 text-xs text-muted-foreground">
                  No matching members.
                </p>
              )}
              {loading && (
                <p role="status" className="px-3 py-4 text-xs text-muted-foreground">
                  Loading members…
                </p>
              )}
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}
