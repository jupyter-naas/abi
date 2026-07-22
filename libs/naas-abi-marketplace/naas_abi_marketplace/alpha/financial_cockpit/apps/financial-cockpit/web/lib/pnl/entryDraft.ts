export function isBudgetEntryDraftReady(entry: {
  organization_slug: string;
  month: string;
  famille_2: string;
  amount: number;
}): boolean {
  return Boolean(
    entry.organization_slug.trim() &&
      /^\d{4}-\d{2}$/.test(entry.month.trim()) &&
      entry.famille_2.trim() &&
      Number.isFinite(entry.amount) &&
      entry.amount !== 0,
  );
}

export function isAdjustmentDraftReady(entry: {
  organization_slug: string;
  month: string;
  famille_2: string;
}): boolean {
  return Boolean(
    entry.organization_slug.trim() &&
      /^\d{4}-\d{2}$/.test(entry.month.trim()) &&
      entry.famille_2.trim(),
  );
}
