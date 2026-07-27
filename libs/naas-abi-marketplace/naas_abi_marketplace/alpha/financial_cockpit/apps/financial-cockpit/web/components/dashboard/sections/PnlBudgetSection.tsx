'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { organizationOptionsFor, perimeterSlugsFor } from '@/lib/pnl/perimeter';
import {
  adjustmentsToEntries,
  applyBudgetLineEntry,
  budgetRowsToEntries,
  buildBudgetOverview,
  clearBudgetMonth,
  MONTH_LABELS,
  monthlyTotals,
  PNL_SCENARIO_ADJUST,
  PNL_SCENARIO_BUD,
  type BudgetLineEntry,
} from '@/lib/pnl/budgetEntries';
import { PNL_FAMILLES, type PnlAdjustment, type PnlBudgetRow } from '@/lib/pnl/model';
import type { ParsedPnlImportRow } from '@/lib/pnl/entryImport';
import { isBudgetEntryDraftReady } from '@/lib/pnl/entryDraft';
import {
  referentialCategorie2Options,
  referentialFamilleOptions,
  referentialThirdpartyOptions,
  validateReferentialEntry,
} from '@/lib/pnl/referentials';
import { useReferentials } from '@/lib/pnl/useReferentials';
import { PageTitle } from '@/components/layout/PageTitle';
import { Button } from '@/components/ui/Button';
import { PnlEntryImportDialog } from '@/components/dashboard/pnl/PnlEntryImportDialog';

const inputClass =
  'w-full min-w-[7rem] rounded border border-transparent bg-transparent px-1.5 py-1 text-sm text-[var(--text)] transition-colors hover:border-[var(--border)] focus:border-[var(--secondary)] focus:bg-[var(--surface)] focus:outline-none';

const readOnlyClass = 'px-1.5 py-1 text-sm text-[var(--text-muted)] whitespace-nowrap';

const currencyFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
});

function formatAmount(value: number): string {
  return currencyFormatter.format(value);
}

function formatLogTimestamp(iso: string): string {
  if (!iso) {
    return '—';
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const pad = (part: number) => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function emptyDraft(organizationSlug: string, company: string, year: string): BudgetLineEntry {
  const now = new Date();
  const month = `${year}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  return {
    key: 'draft',
    scenario: PNL_SCENARIO_BUD,
    organization_slug: organizationSlug,
    company,
    famille_2: PNL_FAMILLES[0].value,
    categorie_2: '',
    categorie_3: '',
    thirdparty: '',
    month,
    amount: 0,
    user: '',
    date_edited: '',
  };
}

const ENTRY_COLUMN_COUNT = 12;

export function PnlBudgetSection({ entity, company, site }: SectionProps) {
  const orgOptions = useMemo(() => organizationOptionsFor(entity, company), [entity, company]);
  const perimeterSlugs = useMemo(() => perimeterSlugsFor(entity, company), [entity, company]);
  const companyBySlug = useMemo(
    () => new Map(orgOptions.map((option) => [option.slug, option.label])),
    [orgOptions],
  );

  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [budgetRows, setBudgetRows] = useState<PnlBudgetRow[]>([]);
  const [adjustments, setAdjustments] = useState<PnlAdjustment[]>([]);
  const [draft, setDraft] = useState<BudgetLineEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const { index: referentialsIndex } = useReferentials({
    entitySlug: entity.url_slug,
    companySlug: company?.organization_slug ?? null,
  });

  const familleOptions = useMemo(
    () =>
      referentialsIndex
        ? referentialFamilleOptions(referentialsIndex)
        : PNL_FAMILLES.map((famille) => famille.value),
    [referentialsIndex],
  );

  const thirdpartyOptions = useMemo(
    () => (referentialsIndex ? referentialThirdpartyOptions(referentialsIndex) : []),
    [referentialsIndex],
  );

  function validateAgainstReferentials(values: {
    thirdparty: string;
    famille_2: string;
    categorie_2: string;
    categorie_3?: string;
  }): { ok: true; normalized: typeof values } | { ok: false } {
    if (!referentialsIndex) {
      return { ok: true, normalized: values };
    }
    const result = validateReferentialEntry(referentialsIndex, values);
    if (!result.valid) {
      setError(result.errors.join(' · '));
      return { ok: false };
    }
    return { ok: true, normalized: { ...values, ...result.normalized } };
  }

  const refreshEntries = useCallback(async () => {
    const [budgetResponse, adjustmentsResponse] = await Promise.all([
      fetch(`/api/entities/${entity.url_slug}/pnl/budget`),
      fetch(`/api/entities/${entity.url_slug}/pnl/adjustments`),
    ]);
    const budgetBody = budgetResponse.ok ? await budgetResponse.json() : { records: [] };
    const adjustmentsBody = adjustmentsResponse.ok
      ? await adjustmentsResponse.json()
      : { records: [] };
    const allBudget: PnlBudgetRow[] = Array.isArray(budgetBody.records) ? budgetBody.records : [];
    const allAdjustments: PnlAdjustment[] = Array.isArray(adjustmentsBody.records)
      ? adjustmentsBody.records
      : [];
    setBudgetRows(allBudget.filter((row) => perimeterSlugs.has(row.organization_slug)));
    setAdjustments(allAdjustments.filter((row) => perimeterSlugs.has(row.organization_slug)));
  }, [entity.url_slug, perimeterSlugs]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      await refreshEntries();
    } catch {
      setError('Impossible de charger le budget.');
    } finally {
      setLoading(false);
    }
  }, [refreshEntries]);

  useEffect(() => {
    void load();
  }, [load]);

  const budEntries = useMemo(
    () => budgetRowsToEntries(budgetRows, companyBySlug, year),
    [budgetRows, companyBySlug, year],
  );
  const adjustEntries = useMemo(
    () => adjustmentsToEntries(adjustments, year),
    [adjustments, year],
  );
  const allSourceEntries = useMemo(
    () => [...budEntries, ...adjustEntries],
    [budEntries, adjustEntries],
  );
  const overviewRows = useMemo(() => buildBudgetOverview(allSourceEntries), [allSourceEntries]);
  const overviewTotals = useMemo(() => monthlyTotals(overviewRows), [overviewRows]);

  const entryRows = useMemo(() => {
    const sorted = [...budEntries, ...adjustEntries].sort((a, b) =>
      a.date_edited < b.date_edited ? 1 : -1,
    );
    return draft ? [...sorted, draft] : sorted;
  }, [budEntries, adjustEntries, draft]);

  async function persistBudgetRow(row: PnlBudgetRow): Promise<PnlBudgetRow | null> {
    const response = await fetch(`/api/entities/${entity.url_slug}/pnl/budget`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(row),
    });
    if (!response.ok) {
      setError("Échec de l'enregistrement de la ligne.");
      return null;
    }
    const body = await response.json();
    return body.record as PnlBudgetRow;
  }

  function patchDraft(patch: Partial<BudgetLineEntry>) {
    setDraft((current) => (current ? { ...current, ...patch } : current));
  }

  async function saveDraft(patch?: Partial<BudgetLineEntry>) {
    const next = draft ? { ...draft, ...patch } : null;
    if (!next) {
      return;
    }
    if (patch) {
      setDraft(next);
    }
    if (!isBudgetEntryDraftReady(next)) {
      setError('Complétez Famille_2, Date et Amount (non nul) avant enregistrement.');
      return;
    }
    const validated = validateAgainstReferentials({
      thirdparty: next.thirdparty,
      famille_2: next.famille_2,
      categorie_2: next.categorie_2,
      categorie_3: next.categorie_3,
    });
    if (!validated.ok) {
      return;
    }
    next.thirdparty = validated.normalized.thirdparty ?? next.thirdparty;
    next.famille_2 = validated.normalized.famille_2 ?? next.famille_2;
    next.categorie_2 = validated.normalized.categorie_2 ?? next.categorie_2;
    next.categorie_3 = validated.normalized.categorie_3 ?? next.categorie_3;
    setError(null);
    const payload = applyBudgetLineEntry(budgetRows, next);
    const saved = await persistBudgetRow(payload);
    if (saved) {
      setDraft(null);
      await refreshEntries();
    }
  }

  async function commitExisting(entry: BudgetLineEntry, patch: Partial<BudgetLineEntry>) {
    if (entry.scenario !== PNL_SCENARIO_BUD || !entry.budgetRowId) {
      return;
    }
    const next = { ...entry, ...patch };
    const validated = validateAgainstReferentials({
      thirdparty: next.thirdparty,
      famille_2: next.famille_2,
      categorie_2: next.categorie_2,
      categorie_3: next.categorie_3,
    });
    if (!validated.ok) {
      return;
    }
    next.thirdparty = validated.normalized.thirdparty ?? next.thirdparty;
    next.famille_2 = validated.normalized.famille_2 ?? next.famille_2;
    next.categorie_2 = validated.normalized.categorie_2 ?? next.categorie_2;
    next.categorie_3 = validated.normalized.categorie_3 ?? next.categorie_3;
    const moved =
      next.organization_slug !== entry.organization_slug ||
      next.famille_2 !== entry.famille_2 ||
      next.categorie_2 !== entry.categorie_2 ||
      next.thirdparty !== entry.thirdparty ||
      next.month !== entry.month;

    let rows = budgetRows;
    if (moved) {
      const cleared = clearBudgetMonth(rows, entry);
      if (cleared) {
        const allZero = cleared.months.every((value) => value === 0);
        if (allZero) {
          const response = await fetch(`/api/entities/${entity.url_slug}/pnl/budget`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: cleared.id }),
          });
          if (response.ok) {
            rows = rows.filter((row) => row.id !== cleared.id);
          }
        } else {
          const saved = await persistBudgetRow(cleared);
          if (saved) {
            rows = rows.map((row) => (row.id === saved.id ? saved : row));
          }
        }
      }
    }

    const payload = applyBudgetLineEntry(rows, next);
    const saved = await persistBudgetRow(payload);
    if (saved) {
      setBudgetRows((current) => {
        let updated = current;
        if (moved && entry.budgetRowId) {
          const clearedLocal = clearBudgetMonth(current, entry);
          if (clearedLocal) {
            updated = clearedLocal.months.every((value) => value === 0)
              ? current.filter((row) => row.id !== clearedLocal.id)
              : current.map((row) => (row.id === clearedLocal.id ? clearedLocal : row));
          }
        }
        const existingIndex = updated.findIndex((row) => row.id === saved.id);
        if (existingIndex >= 0) {
          const copy = [...updated];
          copy[existingIndex] = saved;
          return copy;
        }
        return [...updated, saved];
      });
    }
  }

  async function deleteEntry(entry: BudgetLineEntry) {
    if (entry.scenario !== PNL_SCENARIO_BUD) {
      return;
    }
    if (!entry.budgetRowId) {
      setDraft(null);
      return;
    }
    const cleared = clearBudgetMonth(budgetRows, entry);
    if (!cleared) {
      return;
    }
    const allZero = cleared.months.every((value) => value === 0);
    if (allZero) {
      const response = await fetch(`/api/entities/${entity.url_slug}/pnl/budget`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: cleared.id }),
      });
      if (response.ok) {
        setBudgetRows((rows) => rows.filter((row) => row.id !== cleared.id));
      }
      return;
    }
    const saved = await persistBudgetRow(cleared);
    if (saved) {
      setBudgetRows((rows) => rows.map((row) => (row.id === saved.id ? saved : row)));
    }
  }

  async function importBudgetEntries(entries: ParsedPnlImportRow[]) {
    let imported = 0;
    let failed = 0;
    let rows = budgetRows;

    for (const entry of entries) {
      const payload = applyBudgetLineEntry(rows, {
        organization_slug: entry.organization_slug,
        famille_2: entry.famille_2,
        categorie_2: entry.categorie_2,
        thirdparty: entry.thirdparty,
        month: entry.month,
        amount: entry.amount,
      });
      const saved = await persistBudgetRow(payload);
      if (saved) {
        imported += 1;
        const index = rows.findIndex((row) => row.id === saved.id);
        if (index >= 0) {
          const copy = [...rows];
          copy[index] = saved;
          rows = copy;
        } else {
          rows = [...rows, saved];
        }
      } else {
        failed += 1;
      }
    }

    if (imported > 0) {
      setError(null);
      await refreshEntries();
    }

    return { imported, failed };
  }

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const overviewColSpan = 5 + MONTH_LABELS.length;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint="Vue agrégée du budget (BUD) et des ajustements (ADJUST) par famille, catégorie 2 et tiers — saisissez les écritures BUD ci-dessous.">
          Budget{perimeterSuffix}
        </PageTitle>
      </div>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
          Année
          <input
            className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm text-[var(--text)]"
            value={year}
            onChange={(event) => setYear(event.target.value.trim())}
            placeholder="2026"
          />
        </label>
      </div>

      {error ? <p className="mb-4 text-sm text-red-500">{error}</p> : null}

      <div className="mb-10">
        <h2 className="type-title-4 mb-4">Vue d&apos;ensemble</h2>
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="bg-[var(--secondary)] text-white">
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Scenario
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Famille_2
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Categorie_2
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Thirdparty
                </th>
                {MONTH_LABELS.map((label) => (
                  <th
                    key={label}
                    className="px-2 py-2 text-right text-xs font-semibold uppercase whitespace-nowrap"
                  >
                    {label}
                  </th>
                ))}
                <th className="px-3 py-2 text-right text-xs font-semibold uppercase whitespace-nowrap">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td className="px-3 py-6 text-center text-[var(--text-muted)]" colSpan={overviewColSpan}>
                    Chargement…
                  </td>
                </tr>
              ) : overviewRows.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center text-[var(--text-muted)]" colSpan={overviewColSpan}>
                    Aucune donnée budget / ajustement pour {year}.
                  </td>
                </tr>
              ) : (
                <>
                  {overviewRows.map((row) => (
                    <tr key={row.key} className="border-b border-[var(--border)]">
                      <td className={readOnlyClass}>{row.scenario}</td>
                      <td className={readOnlyClass}>{row.famille_2}</td>
                      <td className={readOnlyClass}>{row.categorie_2 || '—'}</td>
                      <td className={readOnlyClass}>{row.thirdparty || '—'}</td>
                      {row.months.map((value, index) => (
                        <td key={index} className="px-2 py-1.5 text-right whitespace-nowrap">
                          {value ? formatAmount(value) : '—'}
                        </td>
                      ))}
                      <td className="px-3 py-1.5 text-right font-medium whitespace-nowrap">
                        {formatAmount(row.total)}
                      </td>
                    </tr>
                  ))}
                  <tr className="border-t border-[var(--border)] bg-[var(--accent)] font-semibold">
                    <td className="px-3 py-2" colSpan={4}>
                      Total mensuel
                    </td>
                    {overviewTotals.months.map((value, index) => (
                      <td key={index} className="px-2 py-2 text-right whitespace-nowrap">
                        {value ? formatAmount(value) : '—'}
                      </td>
                    ))}
                    <td className="px-3 py-2 text-right whitespace-nowrap">
                      {formatAmount(overviewTotals.total)}
                    </td>
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="type-title-4">Ecritures budget</h2>
          <div className="flex shrink-0 gap-2">
            <Button
              variant="ghost"
              className="!w-auto px-4"
              onPress={() => setImportOpen(true)}
            >
              Importer
            </Button>
            <Button
              className="!w-auto px-4"
              onPress={() =>
                setDraft(emptyDraft(orgOptions[0]?.slug ?? '', orgOptions[0]?.label ?? '', year))
              }
              isDisabled={draft !== null}
            >
              + Ajouter une ligne
            </Button>
          </div>
        </div>

        <PnlEntryImportDialog
          isOpen={importOpen}
          onOpenChange={setImportOpen}
          title="Importer des écritures budget (BUD)"
          orgOptions={orgOptions}
          includeCategorie3={false}
          defaultOrganizationSlug={orgOptions[0]?.slug}
          referentialsIndex={referentialsIndex}
          onImport={importBudgetEntries}
        />

        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          {thirdpartyOptions.length > 0 ? (
            <datalist id="budget-thirdparties">
              {thirdpartyOptions.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          ) : null}
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="bg-[var(--secondary)] text-white">
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Modifié le
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Utilisateur
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Scenario
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Source
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Company
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Thirdparty
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Famille_2
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Categorie_2
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Categorie_3
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                  Date
                </th>
                <th className="px-3 py-2 text-right text-xs font-semibold uppercase whitespace-nowrap">
                  Amount
                </th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td className="px-3 py-6 text-center text-[var(--text-muted)]" colSpan={ENTRY_COLUMN_COUNT}>
                    Chargement…
                  </td>
                </tr>
              ) : entryRows.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center text-[var(--text-muted)]" colSpan={ENTRY_COLUMN_COUNT}>
                    Aucune écriture pour {year}.
                  </td>
                </tr>
              ) : (
                entryRows.map((row) => {
                  const isDraft = row.key === 'draft';
                  const isEditable = row.scenario === PNL_SCENARIO_BUD;
                  const categorie2Options = referentialsIndex
                    ? referentialCategorie2Options(referentialsIndex, row.famille_2)
                    : [];
                  return (
                    <tr key={row.key} className="border-b border-[var(--border)]">
                      <td className={readOnlyClass}>{formatLogTimestamp(row.date_edited)}</td>
                      <td className={readOnlyClass}>{row.user || '—'}</td>
                      <td className={readOnlyClass}>{row.scenario}</td>
                      <td className={readOnlyClass}>
                        {row.scenario === PNL_SCENARIO_BUD ? 'Budget' : 'Ajustement'}
                      </td>
                      <td className="px-1 py-1">
                        {isEditable && orgOptions.length > 1 ? (
                          <select
                            className={inputClass}
                            value={row.organization_slug}
                            onChange={(event) => {
                              const option = orgOptions.find((o) => o.slug === event.target.value);
                              const patch = {
                                organization_slug: event.target.value,
                                company: option?.label ?? '',
                              };
                              if (isDraft) {
                                patchDraft(patch);
                              } else {
                                void commitExisting(row, patch);
                              }
                            }}
                          >
                            {orgOptions.map((option) => (
                              <option key={option.slug} value={option.slug}>
                                {formatEntityName(option.label)}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className={readOnlyClass}>{formatEntityName(row.company)}</span>
                        )}
                      </td>
                      <td className="px-1 py-1">
                        {isEditable ? (
                          <input
                            className={inputClass}
                            list={thirdpartyOptions.length > 0 ? 'budget-thirdparties' : undefined}
                            value={row.thirdparty}
                            onChange={(event) => patchDraft({ thirdparty: event.target.value })}
                            onBlur={(event) =>
                              isDraft
                                ? patchDraft({ thirdparty: event.target.value })
                                : commitExisting(row, { thirdparty: event.target.value })
                            }
                          />
                        ) : (
                          <span className={readOnlyClass}>{row.thirdparty || '—'}</span>
                        )}
                      </td>
                      <td className="px-1 py-1">
                        {isEditable ? (
                          <select
                            className={inputClass}
                            value={row.famille_2}
                            onChange={(event) => {
                              const patch = { famille_2: event.target.value, categorie_2: '' };
                              if (isDraft) {
                                patchDraft(patch);
                              } else {
                                void commitExisting(row, patch);
                              }
                            }}
                          >
                            {familleOptions.map((famille) => (
                              <option key={famille} value={famille}>
                                {famille}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className={readOnlyClass}>{row.famille_2}</span>
                        )}
                      </td>
                      <td className="px-1 py-1">
                        {isEditable ? (
                          categorie2Options.length > 0 ? (
                            <select
                              className={inputClass}
                              value={row.categorie_2}
                              onChange={(event) => {
                                const patch = { categorie_2: event.target.value };
                                if (isDraft) {
                                  patchDraft(patch);
                                } else {
                                  void commitExisting(row, patch);
                                }
                              }}
                            >
                              <option value="">—</option>
                              {categorie2Options.map((label) => (
                                <option key={label} value={label}>
                                  {label}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <input
                              className={inputClass}
                              value={row.categorie_2}
                              onChange={(event) => patchDraft({ categorie_2: event.target.value })}
                              onBlur={(event) =>
                                isDraft
                                  ? patchDraft({ categorie_2: event.target.value })
                                  : commitExisting(row, { categorie_2: event.target.value })
                              }
                            />
                          )
                        ) : (
                          <span className={readOnlyClass}>{row.categorie_2 || '—'}</span>
                        )}
                      </td>
                      <td className="px-1 py-1">
                        {isEditable ? (
                          <input
                            className={inputClass}
                            value={row.categorie_3}
                            onChange={(event) => patchDraft({ categorie_3: event.target.value })}
                            onBlur={(event) =>
                              isDraft
                                ? patchDraft({ categorie_3: event.target.value })
                                : commitExisting(row, { categorie_3: event.target.value })
                            }
                          />
                        ) : (
                          <span className={readOnlyClass}>{row.categorie_3 || '—'}</span>
                        )}
                      </td>
                      <td className="px-1 py-1">
                        {isEditable ? (
                          <input
                            type="month"
                            className={inputClass}
                            value={row.month}
                            onChange={(event) => {
                              const patch = { month: event.target.value };
                              if (isDraft) {
                                patchDraft(patch);
                              } else {
                                void commitExisting(row, patch);
                              }
                            }}
                          />
                        ) : (
                          <span className={readOnlyClass}>{row.month}</span>
                        )}
                      </td>
                      <td className="px-1 py-1">
                        {isEditable ? (
                          <input
                            type="number"
                            step="0.01"
                            className={`${inputClass} text-right`}
                            value={row.amount}
                            onChange={(event) => patchDraft({ amount: Number(event.target.value) })}
                            onBlur={(event) =>
                              isDraft
                                ? void saveDraft({ amount: Number(event.target.value) })
                                : commitExisting(row, { amount: Number(event.target.value) })
                            }
                          />
                        ) : (
                          <span className={`${readOnlyClass} block text-right`}>
                            {formatAmount(row.amount)}
                          </span>
                        )}
                      </td>
                      <td className="px-1 py-1 text-center">
                        {isEditable ? (
                          <div className="flex items-center justify-center gap-1">
                            {isDraft ? (
                              <button
                                type="button"
                                onClick={() => void saveDraft()}
                                className="text-[var(--secondary)] hover:text-[var(--text)]"
                                aria-label="Enregistrer la ligne"
                                title="Enregistrer"
                              >
                                ✓
                              </button>
                            ) : null}
                            <button
                              type="button"
                              onClick={() => deleteEntry(row)}
                              className="text-[var(--text-muted)] hover:text-red-500"
                              aria-label={isDraft ? 'Annuler la ligne' : 'Supprimer la ligne'}
                            >
                              ✕
                            </button>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-[var(--text-muted)]">
          Les écritures ADJUST proviennent des ajustements comptables (lecture seule). Les
          écritures BUD alimentent la vue d&apos;ensemble ci-dessus et sont persistées localement.
        </p>
      </div>
    </div>
  );
}
