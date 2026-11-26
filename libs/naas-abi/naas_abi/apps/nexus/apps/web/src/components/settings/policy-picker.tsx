'use client';

/**
 * Which policy of the workspace a page edits (Access › Features, Access › Modules): "<W> access",
 * the workspace's offer, first; or another policy the workspace owns, what it grants its holders.
 */
export type PickablePolicy = { id: string; name: string };

export function PolicyPicker({
  policies,
  value,
  onChange,
  disabled = false,
}: {
  policies: readonly PickablePolicy[] | undefined;
  /** The policy edited. */
  value: string | null | undefined;
  onChange: (policyId: string) => void;
  disabled?: boolean;
}) {
  if (!policies || policies.length === 0) return null;
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">Policy</span>
      <select
        aria-label="Policy"
        title="The policy edited"
        data-field="policy"
        className="h-9 max-w-[16rem] rounded-none border border-input bg-background px-3 text-sm text-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
        value={value ?? policies[0].id}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {policies.map((policy) => (
          <option key={policy.id} value={policy.id}>
            {policy.name}
          </option>
        ))}
      </select>
    </label>
  );
}
