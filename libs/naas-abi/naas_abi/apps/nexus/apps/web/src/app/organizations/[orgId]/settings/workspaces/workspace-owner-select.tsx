'use client';

import { useEffect, useMemo, useState } from 'react';
import { authFetch } from '@/stores/auth';

export type OrgMemberOption = {
  userId: string;
  email: string;
  name?: string;
};

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
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);

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

  const filtered = useMemo(() => {
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

  return (
    <div className="space-y-2">
      <input
        type="search"
        placeholder="Search by name or email…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        disabled={disabled || loading}
        className="account-profile-field-input"
        aria-label="Search organization members"
      />
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled || loading || filtered.length === 0}
        className="account-profile-field-input"
        aria-label="Workspace owner"
      >
        {filtered.map((member) => (
          <option key={member.userId} value={member.userId}>
            {member.name ? `${member.name} · ${member.email}` : member.email}
          </option>
        ))}
      </select>
      {selected && (
        <p className="text-xs text-muted-foreground">
          Owner: {selected.email}
        </p>
      )}
    </div>
  );
}
