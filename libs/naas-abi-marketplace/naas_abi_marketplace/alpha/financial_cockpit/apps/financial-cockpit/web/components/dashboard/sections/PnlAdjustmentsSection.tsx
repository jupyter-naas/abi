'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { organizationOptionsFor, perimeterSlugsFor } from '@/lib/pnl/perimeter';
import { PNL_FAMILLES, type PnlAdjustment } from '@/lib/pnl/model';
import { PNL_SCENARIO_ADJUST } from '@/lib/pnl/budgetEntries';
import type { ParsedPnlImportRow } from '@/lib/pnl/entryImport';
import { isAdjustmentDraftReady } from '@/lib/pnl/entryDraft';
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

const ADJUSTMENT_SOURCE = 'Ajustement';

const COLUMN_COUNT = 15;

/** Local-time `YYYY-MM-DD HH:mm:ss` — readable and still sorts chronologically. */
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

function emptyDraft(organizationSlug: string, company: string): PnlAdjustment {
  const now = new Date();
  const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  return {
    id: '',
    organization_slug: organizationSlug,
    company,
    famille_2: PNL_FAMILLES[0].value,
    categorie_2: '',
    categorie_3: '',
    thirdparty: '',
    label: '',
    entry_type: '',
    action: '',
    comments: '',
    month,
    amount: 0,
    user: '',
    date_edited: '',
  };
}

export function PnlAdjustmentsSection({ entity, company, site }: SectionProps) {
  const orgOptions = useMemo(() => organizationOptionsFor(entity, company), [entity, company]);
  const perimeterSlugs = useMemo(() => perimeterSlugsFor(entity, company), [entity, company]);

  const [rows, setRows] = useState<PnlAdjustment[]>([]);
  const [draft, setDraft] = useState<PnlAdjustment | null>(null);
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
    categorie_3: string;
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

  const refreshRows = useCallback(async () => {
    const response = await fetch(`/api/entities/${entity.url_slug}/pnl/adjustments`);
    const body = response.ok ? await response.json() : { records: [] };
    const all: PnlAdjustment[] = Array.isArray(body.records) ? body.records : [];
    setRows(all.filter((row) => perimeterSlugs.has(row.organization_slug)));
  }, [entity.url_slug, perimeterSlugs]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      await refreshRows();
    } catch {
      setError('Impossible de charger les ajustements.');
    } finally {
      setLoading(false);
    }
  }, [refreshRows]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Live-update the input value on every keystroke, without saving yet. */
  function setLocal(id: string, patch: Partial<PnlAdjustment>) {
    if (id === '') {
      setDraft((current) => (current ? { ...current, ...patch } : current));
      return;
    }
    setRows((current) => current.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }

  async function persist(row: PnlAdjustment): Promise<PnlAdjustment | null> {
    const response = await fetch(`/api/entities/${entity.url_slug}/pnl/adjustments`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(row),
    });
    if (!response.ok) {
      setError("Échec de l'enregistrement de la ligne.");
      return null;
    }
    const body = await response.json();
    return body.record as PnlAdjustment;
  }

  /** Commit an existing row to the server. Draft rows stay local until saveDraft. */
  async function commit(id: string, patch: Partial<PnlAdjustment>) {
    if (id === '') {
      setDraft((current) => (current ? { ...current, ...patch } : current));
      return;
    }
    const current = rows.find((row) => row.id === id);
    if (!current) {
      return;
    }
    const next = { ...current, ...patch };
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
    setRows((rowsCurrent) => rowsCurrent.map((row) => (row.id === id ? next : row)));
    const saved = await persist(next);
    if (saved) {
      setRows((rowsCurrent) => rowsCurrent.map((row) => (row.id === id ? saved : row)));
    }
  }

  async function saveDraft(patch?: Partial<PnlAdjustment>) {
    const next = draft ? { ...draft, ...patch } : null;
    if (!next) {
      return;
    }
    if (patch) {
      setDraft(next);
    }
    if (!isAdjustmentDraftReady(next)) {
      setError('Complétez Company, Famille_2 et Date avant enregistrement.');
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
    const saved = await persist(next);
    if (saved) {
      setDraft(null);
      await refreshRows();
    }
  }

  async function deleteRow(id: string) {
    const response = await fetch(`/api/entities/${entity.url_slug}/pnl/adjustments`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    });
    if (response.ok) {
      setRows((current) => current.filter((row) => row.id !== id));
    }
  }

  async function importRows(entries: ParsedPnlImportRow[]) {
    let imported = 0;
    let failed = 0;

    for (const entry of entries) {
      const row: PnlAdjustment = {
        id: '',
        organization_slug: entry.organization_slug,
        company: entry.company,
        famille_2: entry.famille_2,
        categorie_2: entry.categorie_2,
        categorie_3: entry.categorie_3,
        thirdparty: entry.thirdparty,
        label: '',
        entry_type: '',
        action: '',
        comments: '',
        month: entry.month,
        amount: entry.amount,
        user: '',
        date_edited: '',
      };
      const saved = await persist(row);
      if (saved) {
        imported += 1;
      } else {
        failed += 1;
      }
    }

    if (imported > 0) {
      setError(null);
      await refreshRows();
    }

    return { imported, failed };
  }

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const allRows = useMemo(() => {
    const sorted = [...rows].sort((a, b) => (a.date_edited < b.date_edited ? 1 : -1));
    return draft ? [...sorted, draft] : sorted;
  }, [rows, draft]);

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint="Ajustements comptables manuels fusionnés dans les actuals du compte de résultat (écarts constatés vs source).">
          Ecritures ajustements{perimeterSuffix}
        </PageTitle>
      </div>

      <div className="mb-4 flex justify-end gap-2">
        <Button
          variant="ghost"
          className="!w-auto shrink-0 px-4"
          onPress={() => setImportOpen(true)}
        >
          Importer
        </Button>
        <Button
          className="!w-auto shrink-0 px-4"
          onPress={() => setDraft(emptyDraft(orgOptions[0]?.slug ?? '', orgOptions[0]?.label ?? ''))}
          isDisabled={draft !== null}
        >
          + Ajouter une ligne
        </Button>
      </div>

      <PnlEntryImportDialog
        isOpen={importOpen}
        onOpenChange={setImportOpen}
        title="Importer des écritures d'ajustements"
        orgOptions={orgOptions}
        includeCategorie3
        defaultOrganizationSlug={orgOptions[0]?.slug}
        referentialsIndex={referentialsIndex}
        onImport={importRows}
      />

      {error ? <p className="mb-4 text-sm text-red-500">{error}</p> : null}

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        {thirdpartyOptions.length > 0 ? (
          <datalist id="adjustment-thirdparties">
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
                Type d&apos;écriture
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                Action
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase whitespace-nowrap">
                Commentaires
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
                <td className="px-3 py-6 text-center text-[var(--text-muted)]" colSpan={COLUMN_COUNT}>
                  Chargement…
                </td>
              </tr>
            ) : allRows.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-center text-[var(--text-muted)]" colSpan={COLUMN_COUNT}>
                  Aucun ajustement pour ce périmètre.
                </td>
              </tr>
            ) : (
              allRows.map((row) => {
                const isDraft = row.id === '';
                const categorie2Options = referentialsIndex
                  ? referentialCategorie2Options(referentialsIndex, row.famille_2)
                  : [];
                return (
                  <tr key={row.id || 'draft'} className="border-b border-[var(--border)]">
                    <td className={readOnlyClass}>{formatLogTimestamp(row.date_edited)}</td>
                    <td className={readOnlyClass}>{row.user || '—'}</td>
                    <td className={readOnlyClass}>{PNL_SCENARIO_ADJUST}</td>
                    <td className={readOnlyClass}>{ADJUSTMENT_SOURCE}</td>
                    <td className="px-1 py-1">
                      <input
                        className={inputClass}
                        value={row.entry_type}
                        onChange={(event) => setLocal(row.id, { entry_type: event.target.value })}
                        onBlur={(event) =>
                          isDraft
                            ? setLocal(row.id, { entry_type: event.target.value })
                            : commit(row.id, { entry_type: event.target.value })
                        }
                      />
                    </td>
                    <td className="px-1 py-1">
                      <input
                        className={inputClass}
                        value={row.action}
                        onChange={(event) => setLocal(row.id, { action: event.target.value })}
                        onBlur={(event) =>
                          isDraft
                            ? setLocal(row.id, { action: event.target.value })
                            : commit(row.id, { action: event.target.value })
                        }
                      />
                    </td>
                    <td className="px-1 py-1">
                      <input
                        className={inputClass}
                        value={row.comments}
                        onChange={(event) => setLocal(row.id, { comments: event.target.value })}
                        onBlur={(event) =>
                          isDraft
                            ? setLocal(row.id, { comments: event.target.value })
                            : commit(row.id, { comments: event.target.value })
                        }
                      />
                    </td>
                    <td className="px-1 py-1">
                      {orgOptions.length > 1 ? (
                        <select
                          className={inputClass}
                          value={row.organization_slug}
                          onChange={(event) => {
                            const option = orgOptions.find((o) => o.slug === event.target.value);
                            const patch = {
                              organization_slug: event.target.value,
                              company: option?.label ?? '',
                            };
                            setLocal(row.id, patch);
                            if (!isDraft) {
                              void commit(row.id, patch);
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
                      <input
                        className={inputClass}
                        list={thirdpartyOptions.length > 0 ? 'adjustment-thirdparties' : undefined}
                        value={row.thirdparty}
                        onChange={(event) => setLocal(row.id, { thirdparty: event.target.value })}
                        onBlur={(event) =>
                          isDraft
                            ? setLocal(row.id, { thirdparty: event.target.value })
                            : commit(row.id, { thirdparty: event.target.value })
                        }
                      />
                    </td>
                    <td className="px-1 py-1">
                      <select
                        className={inputClass}
                        value={row.famille_2}
                        onChange={(event) => {
                          setLocal(row.id, { famille_2: event.target.value, categorie_2: '' });
                          if (!isDraft) {
                            void commit(row.id, { famille_2: event.target.value, categorie_2: '' });
                          }
                        }}
                      >
                        {familleOptions.map((famille) => (
                          <option key={famille} value={famille}>
                            {famille}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-1 py-1">
                      {categorie2Options.length > 0 ? (
                        <select
                          className={inputClass}
                          value={row.categorie_2}
                          onChange={(event) => {
                            setLocal(row.id, { categorie_2: event.target.value });
                            if (!isDraft) {
                              void commit(row.id, { categorie_2: event.target.value });
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
                          onChange={(event) => setLocal(row.id, { categorie_2: event.target.value })}
                          onBlur={(event) =>
                            isDraft
                              ? setLocal(row.id, { categorie_2: event.target.value })
                              : commit(row.id, { categorie_2: event.target.value })
                          }
                        />
                      )}
                    </td>
                    <td className="px-1 py-1">
                      {categorie2Options.length > 0 ? (
                        <select
                          className={inputClass}
                          value={row.categorie_3}
                          onChange={(event) => {
                            setLocal(row.id, { categorie_3: event.target.value });
                            if (!isDraft) {
                              void commit(row.id, { categorie_3: event.target.value });
                            }
                          }}
                        >
                          <option value="">—</option>
                          {categorie2Options.map((label) => (
                            <option key={`c3-${label}`} value={label}>
                              {label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          className={inputClass}
                          value={row.categorie_3}
                          onChange={(event) => setLocal(row.id, { categorie_3: event.target.value })}
                          onBlur={(event) =>
                            isDraft
                              ? setLocal(row.id, { categorie_3: event.target.value })
                              : commit(row.id, { categorie_3: event.target.value })
                          }
                        />
                      )}
                    </td>
                    <td className="px-1 py-1">
                      <input
                        type="month"
                        className={inputClass}
                        value={row.month}
                        onChange={(event) => {
                          setLocal(row.id, { month: event.target.value });
                          if (!isDraft) {
                            void commit(row.id, { month: event.target.value });
                          }
                        }}
                      />
                    </td>
                    <td className="px-1 py-1">
                      <input
                        type="number"
                        step="0.01"
                        className={`${inputClass} text-right`}
                        value={row.amount}
                        onChange={(event) => setLocal(row.id, { amount: Number(event.target.value) })}
                        onBlur={(event) =>
                          isDraft
                            ? void saveDraft({ amount: Number(event.target.value) })
                            : commit(row.id, { amount: Number(event.target.value) })
                        }
                      />
                    </td>
                    <td className="px-1 py-1 text-center">
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
                          onClick={() => (isDraft ? setDraft(null) : deleteRow(row.id))}
                          className="text-[var(--text-muted)] hover:text-red-500"
                          aria-label={isDraft ? 'Annuler la ligne' : 'Supprimer la ligne'}
                        >
                          ✕
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
