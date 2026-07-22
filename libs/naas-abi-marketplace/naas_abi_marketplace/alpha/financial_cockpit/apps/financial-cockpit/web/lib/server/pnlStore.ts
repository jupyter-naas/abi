import 'server-only';

import { readJsonFile, writeJsonFile } from '@/lib/data/storage';
import type { PnlAdjustment, PnlBudgetRow } from '@/lib/pnl/model';

/**
 * P&L adjustments and budget rows are small, hand-entered reference tables —
 * unlike the invoice follow-up log, there is no cross-perimeter replay
 * concern, so each dataset lives in one global JSON array that the editor
 * pages read/modify/write wholesale.
 */
const ADJUSTMENTS_KEY = 'globals/pnl/adjustments.json';
const BUDGET_KEY = 'globals/pnl/budget.json';

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asNumber(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

function parseAdjustment(entry: unknown): PnlAdjustment | null {
  if (!entry || typeof entry !== 'object') {
    return null;
  }
  const row = entry as Record<string, unknown>;
  const id = asString(row.id);
  if (!id) {
    return null;
  }
  return {
    id,
    organization_slug: asString(row.organization_slug),
    company: asString(row.company),
    famille_2: asString(row.famille_2),
    categorie_2: asString(row.categorie_2),
    categorie_3: asString(row.categorie_3),
    thirdparty: asString(row.thirdparty),
    label: asString(row.label),
    entry_type: asString(row.entry_type),
    action: asString(row.action),
    comments: asString(row.comments),
    month: asString(row.month),
    amount: asNumber(row.amount),
    user: asString(row.user),
    date_edited: asString(row.date_edited),
  };
}

function parseBudgetRow(entry: unknown): PnlBudgetRow | null {
  if (!entry || typeof entry !== 'object') {
    return null;
  }
  const row = entry as Record<string, unknown>;
  const id = asString(row.id);
  if (!id) {
    return null;
  }
  const rawMonths = Array.isArray(row.months) ? row.months : [];
  const months = Array.from({ length: 12 }, (_, i) => asNumber(rawMonths[i]));
  return {
    id,
    organization_slug: asString(row.organization_slug),
    famille_2: asString(row.famille_2),
    categorie_2: asString(row.categorie_2),
    thirdparty: asString(row.thirdparty),
    year: asString(row.year),
    months,
    user: asString(row.user),
    date_edited: asString(row.date_edited),
  };
}

export async function listPnlAdjustments(): Promise<PnlAdjustment[]> {
  const raw = await readJsonFile<unknown[]>(ADJUSTMENTS_KEY);
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map(parseAdjustment)
    .filter((row): row is PnlAdjustment => row !== null);
}

export async function listPnlBudgetRows(): Promise<PnlBudgetRow[]> {
  const raw = await readJsonFile<unknown[]>(BUDGET_KEY);
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.map(parseBudgetRow).filter((row): row is PnlBudgetRow => row !== null);
}

export type PnlAdjustmentInput = Omit<PnlAdjustment, 'id' | 'date_edited' | 'user'>;

export async function upsertPnlAdjustment(
  id: string | null,
  input: PnlAdjustmentInput,
  user: string,
): Promise<PnlAdjustment> {
  const rows = await listPnlAdjustments();
  const record: PnlAdjustment = {
    ...input,
    id: id ?? crypto.randomUUID(),
    user,
    date_edited: new Date().toISOString(),
  };
  const index = rows.findIndex((row) => row.id === record.id);
  if (index >= 0) {
    rows[index] = record;
  } else {
    rows.push(record);
  }
  const written = await writeJsonFile(ADJUSTMENTS_KEY, rows);
  if (!written) {
    throw new Error('Failed to persist P&L adjustment');
  }
  return record;
}

export async function deletePnlAdjustment(id: string): Promise<boolean> {
  const rows = await listPnlAdjustments();
  const next = rows.filter((row) => row.id !== id);
  if (next.length === rows.length) {
    return false;
  }
  const written = await writeJsonFile(ADJUSTMENTS_KEY, next);
  if (!written) {
    throw new Error('Failed to persist P&L adjustment');
  }
  return true;
}

export type PnlBudgetRowInput = Omit<PnlBudgetRow, 'id' | 'date_edited' | 'user'>;

export async function upsertPnlBudgetRow(
  id: string | null,
  input: PnlBudgetRowInput,
  user: string,
): Promise<PnlBudgetRow> {
  const rows = await listPnlBudgetRows();
  const record: PnlBudgetRow = {
    ...input,
    id: id ?? crypto.randomUUID(),
    user,
    date_edited: new Date().toISOString(),
  };
  const index = rows.findIndex((row) => row.id === record.id);
  if (index >= 0) {
    rows[index] = record;
  } else {
    rows.push(record);
  }
  const written = await writeJsonFile(BUDGET_KEY, rows);
  if (!written) {
    throw new Error('Failed to persist P&L budget row');
  }
  return record;
}

export async function deletePnlBudgetRow(id: string): Promise<boolean> {
  const rows = await listPnlBudgetRows();
  const next = rows.filter((row) => row.id !== id);
  if (next.length === rows.length) {
    return false;
  }
  const written = await writeJsonFile(BUDGET_KEY, next);
  if (!written) {
    throw new Error('Failed to persist P&L budget row');
  }
  return true;
}
