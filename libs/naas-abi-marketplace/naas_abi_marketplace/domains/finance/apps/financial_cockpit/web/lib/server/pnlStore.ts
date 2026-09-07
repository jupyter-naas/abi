import 'server-only';

import { readJsonFile, writeJsonFile } from '@/lib/data/storage';
import { scopeToPerimeter } from '@/lib/server/perimeterScope';
import type { PnlAdjustment, PnlBudgetRow } from '@/lib/performance/pnl/model';

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

/**
 * Every row in the file, across all perimeters. Internal to this module: the
 * whole array has to be rewritten on each mutation. API handlers must use the
 * perimeter-scoped variants below — see perimeterScope.ts for why.
 */
async function readAllAdjustments(): Promise<PnlAdjustment[]> {
  const raw = await readJsonFile<unknown[]>(ADJUSTMENTS_KEY);
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map(parseAdjustment)
    .filter((row): row is PnlAdjustment => row !== null);
}

async function readAllBudgetRows(): Promise<PnlBudgetRow[]> {
  const raw = await readJsonFile<unknown[]>(BUDGET_KEY);
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.map(parseBudgetRow).filter((row): row is PnlBudgetRow => row !== null);
}

export async function listPnlAdjustments(
  perimeterSlugs: ReadonlySet<string>,
): Promise<PnlAdjustment[]> {
  return scopeToPerimeter(await readAllAdjustments(), perimeterSlugs);
}

export async function listPnlBudgetRows(
  perimeterSlugs: ReadonlySet<string>,
): Promise<PnlBudgetRow[]> {
  return scopeToPerimeter(await readAllBudgetRows(), perimeterSlugs);
}

export type PnlAdjustmentInput = Omit<PnlAdjustment, 'id' | 'date_edited' | 'user'>;

/**
 * Upsert one adjustment. `id` is caller-supplied, so both the row being
 * targeted *and* the row being written must sit inside `perimeterSlugs`;
 * otherwise a user scoped to one perimeter could overwrite another's row or
 * file its own row under someone else's organization. Returns null when either
 * check fails — callers surface that as "not found".
 */
export async function upsertPnlAdjustment(
  id: string | null,
  input: PnlAdjustmentInput,
  user: string,
  perimeterSlugs: ReadonlySet<string>,
): Promise<PnlAdjustment | null> {
  if (!perimeterSlugs.has(input.organization_slug)) {
    return null;
  }

  const rows = await readAllAdjustments();
  const record: PnlAdjustment = {
    ...input,
    id: id ?? crypto.randomUUID(),
    user,
    date_edited: new Date().toISOString(),
  };
  const index = rows.findIndex((row) => row.id === record.id);
  if (index >= 0) {
    if (!perimeterSlugs.has(rows[index].organization_slug)) {
      return null;
    }
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

/** Delete by caller-supplied id — only within the caller's perimeter. */
export async function deletePnlAdjustment(
  id: string,
  perimeterSlugs: ReadonlySet<string>,
): Promise<boolean> {
  const rows = await readAllAdjustments();
  const target = rows.find((row) => row.id === id);
  if (!target || !perimeterSlugs.has(target.organization_slug)) {
    return false;
  }
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

/** Perimeter-scoped upsert — see upsertPnlAdjustment for the rationale. */
export async function upsertPnlBudgetRow(
  id: string | null,
  input: PnlBudgetRowInput,
  user: string,
  perimeterSlugs: ReadonlySet<string>,
): Promise<PnlBudgetRow | null> {
  if (!perimeterSlugs.has(input.organization_slug)) {
    return null;
  }

  const rows = await readAllBudgetRows();
  const record: PnlBudgetRow = {
    ...input,
    id: id ?? crypto.randomUUID(),
    user,
    date_edited: new Date().toISOString(),
  };
  const index = rows.findIndex((row) => row.id === record.id);
  if (index >= 0) {
    if (!perimeterSlugs.has(rows[index].organization_slug)) {
      return null;
    }
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

/** Delete by caller-supplied id — only within the caller's perimeter. */
export async function deletePnlBudgetRow(
  id: string,
  perimeterSlugs: ReadonlySet<string>,
): Promise<boolean> {
  const rows = await readAllBudgetRows();
  const target = rows.find((row) => row.id === id);
  if (!target || !perimeterSlugs.has(target.organization_slug)) {
    return false;
  }
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
