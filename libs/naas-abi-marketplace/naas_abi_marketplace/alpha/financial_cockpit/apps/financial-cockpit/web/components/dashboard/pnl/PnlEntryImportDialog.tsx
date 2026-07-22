'use client';

import { useEffect, useMemo, useState } from 'react';
import { Dialog, Heading, Modal, ModalOverlay } from 'react-aria-components';

import { Button } from '@/components/ui/Button';
import { formatEntityName } from '@/lib/format';
import { readSpreadsheetFile, SPREADSHEET_ACCEPT, type SpreadsheetSheet } from '@/lib/import/spreadsheetImport';
import {
  guessPnlEntryColumnMapping,
  missingRequiredMappings,
  parsePnlImportRows,
  pnlEntryImportFields,
  validPnlImportRows,
  type ParsedPnlImportRow,
  type PnlEntryColumnMapping,
  type PnlEntryImportField,
} from '@/lib/pnl/entryImport';
import type { ReferentialsIndex } from '@/lib/pnl/referentials';
import type { OrganizationOption } from '@/lib/pnl/perimeter';

type PnlEntryImportDialogProps = {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  orgOptions: OrganizationOption[];
  includeCategorie3: boolean;
  defaultOrganizationSlug?: string;
  referentialsIndex?: ReferentialsIndex | null;
  onImport: (rows: ParsedPnlImportRow[]) => Promise<{ imported: number; failed: number }>;
};

const selectClass =
  'w-full rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm text-[var(--text)]';

export function PnlEntryImportDialog({
  isOpen,
  onOpenChange,
  title,
  orgOptions,
  includeCategorie3,
  defaultOrganizationSlug,
  referentialsIndex,
  onImport,
}: PnlEntryImportDialogProps) {
  const fieldSpecs = useMemo(
    () => pnlEntryImportFields(includeCategorie3),
    [includeCategorie3],
  );

  const [fileName, setFileName] = useState('');
  const [sheets, setSheets] = useState<SpreadsheetSheet[]>([]);
  const [selectedSheetName, setSelectedSheetName] = useState('');
  const [mapping, setMapping] = useState<PnlEntryColumnMapping>({});
  const [parseError, setParseError] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [loadingFile, setLoadingFile] = useState(false);

  const activeSheet = useMemo(
    () => sheets.find((sheet) => sheet.name === selectedSheetName) ?? sheets[0] ?? null,
    [sheets, selectedSheetName],
  );

  const parsedRows = useMemo(() => {
    if (!activeSheet) {
      return [];
    }
    return parsePnlImportRows(activeSheet.rows, mapping, orgOptions, {
      includeCategorie3,
      defaultOrganizationSlug,
      referentialsIndex,
    });
  }, [activeSheet, mapping, orgOptions, includeCategorie3, defaultOrganizationSlug, referentialsIndex]);

  const validRows = useMemo(() => validPnlImportRows(parsedRows), [parsedRows]);
  const invalidCount = parsedRows.length - validRows.length;
  const missingMappings = useMemo(
    () => missingRequiredMappings(mapping, orgOptions, includeCategorie3),
    [mapping, orgOptions, includeCategorie3],
  );

  useEffect(() => {
    if (!isOpen) {
      setFileName('');
      setSheets([]);
      setSelectedSheetName('');
      setMapping({});
      setParseError(null);
      setImportError(null);
      setImporting(false);
      setLoadingFile(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!activeSheet) {
      return;
    }
    setMapping((current) => {
      const guessed = guessPnlEntryColumnMapping(activeSheet.headers);
      const hasCurrent = Object.values(current).some(Boolean);
      return hasCurrent ? current : guessed;
    });
  }, [activeSheet]);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) {
      return;
    }

    setLoadingFile(true);
    setParseError(null);
    setImportError(null);
    try {
      const nextSheets = await readSpreadsheetFile(file);
      if (nextSheets.length === 0) {
        setParseError('Aucune feuille ou colonne détectée dans le fichier.');
        setSheets([]);
        setSelectedSheetName('');
        setFileName('');
        return;
      }
      setFileName(file.name);
      setSheets(nextSheets);
      setSelectedSheetName(nextSheets[0].name);
      setMapping(guessPnlEntryColumnMapping(nextSheets[0].headers));
    } catch {
      setParseError('Impossible de lire le fichier. Formats acceptés : CSV, XLS, XLSX.');
      setSheets([]);
      setSelectedSheetName('');
      setFileName('');
    } finally {
      setLoadingFile(false);
    }
  }

  function updateMapping(field: PnlEntryImportField, header: string) {
    setMapping((current) => {
      const next = { ...current };
      if (!header) {
        delete next[field];
      } else {
        next[field] = header;
      }
      return next;
    });
  }

  async function handleImport(close: () => void) {
    if (validRows.length === 0) {
      return;
    }
    setImporting(true);
    setImportError(null);
    try {
      const result = await onImport(validRows);
      if (result.failed > 0 && result.imported === 0) {
        setImportError(`Échec de l'import (${result.failed} ligne(s)).`);
        return;
      }
      close();
    } catch {
      setImportError("Erreur inattendue pendant l'import.");
    } finally {
      setImporting(false);
    }
  }

  const previewRows = parsedRows.slice(0, 8);

  return (
    <ModalOverlay
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      isDismissable={!importing}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 backdrop-blur-[1px]"
    >
      <Modal className="flex w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl outline-none max-h-[92vh]">
        <Dialog className="flex min-h-0 flex-1 flex-col outline-none">
          {({ close }) => (
            <>
              <header className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
                <Heading slot="title" className="truncate text-sm font-semibold text-[var(--text)]">
                  {title}
                </Heading>
                <button
                  type="button"
                  onClick={close}
                  disabled={importing}
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--secondary)] disabled:opacity-50"
                  aria-label="Fermer"
                >
                  <span aria-hidden className="text-lg leading-none">
                    ×
                  </span>
                </button>
              </header>

              <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
                <section>
                  <label className="mb-2 block text-sm font-medium text-[var(--text)]">
                    Fichier local
                  </label>
                  <input
                    type="file"
                    accept={SPREADSHEET_ACCEPT}
                    onChange={(event) => void handleFileChange(event)}
                    disabled={loadingFile || importing}
                    className="block w-full text-sm text-[var(--text-muted)] file:mr-3 file:rounded file:border-0 file:bg-[var(--secondary)] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:opacity-90"
                  />
                  {fileName ? (
                    <p className="mt-2 text-xs text-[var(--text-muted)]">Fichier : {fileName}</p>
                  ) : null}
                  {loadingFile ? (
                    <p className="mt-2 text-xs text-[var(--text-muted)]">Lecture du fichier…</p>
                  ) : null}
                  {parseError ? <p className="mt-2 text-sm text-red-500">{parseError}</p> : null}
                </section>

                {sheets.length > 1 ? (
                  <section>
                    <label className="mb-2 block text-sm font-medium text-[var(--text)]">
                      Feuille Excel
                    </label>
                    <select
                      className={selectClass}
                      value={selectedSheetName}
                      onChange={(event) => {
                        const nextName = event.target.value;
                        setSelectedSheetName(nextName);
                        const sheet = sheets.find((entry) => entry.name === nextName);
                        if (sheet) {
                          setMapping(guessPnlEntryColumnMapping(sheet.headers));
                        }
                      }}
                      disabled={importing}
                    >
                      {sheets.map((sheet) => (
                        <option key={sheet.name} value={sheet.name}>
                          {sheet.name} ({sheet.rows.length} ligne(s))
                        </option>
                      ))}
                    </select>
                  </section>
                ) : null}

                {activeSheet ? (
                  <>
                    <section>
                      <h3 className="mb-3 text-sm font-medium text-[var(--text)]">
                        Rapprochement des colonnes
                      </h3>
                      <div className="grid gap-3 sm:grid-cols-2">
                        {fieldSpecs.map((field) => (
                          <label key={field.key} className="block text-sm">
                            <span className="mb-1 block text-[var(--text-muted)]">
                              {field.label}
                              {field.required ? ' *' : ''}
                            </span>
                            <select
                              className={selectClass}
                              value={mapping[field.key] ?? ''}
                              onChange={(event) => updateMapping(field.key, event.target.value)}
                              disabled={importing}
                            >
                              <option value="">— Non mappé —</option>
                              {activeSheet.headers.map((header) => (
                                <option key={header} value={header}>
                                  {header}
                                </option>
                              ))}
                            </select>
                          </label>
                        ))}
                      </div>
                      {missingMappings.length > 0 ? (
                        <p className="mt-3 text-xs text-amber-600">
                          Colonnes obligatoires manquantes : {missingMappings.join(', ')}
                        </p>
                      ) : null}
                    </section>

                    <section>
                      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
                        <span className="text-[var(--text)]">
                          {validRows.length} ligne(s) valide(s)
                        </span>
                        {invalidCount > 0 ? (
                          <span className="text-red-500">{invalidCount} ligne(s) en erreur</span>
                        ) : null}
                        <span className="text-[var(--text-muted)]">
                          {activeSheet.rows.length} ligne(s) lues
                        </span>
                      </div>

                      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
                        <table className="min-w-full border-collapse text-xs">
                          <thead>
                            <tr className="bg-[var(--accent)] text-[var(--text)]">
                              <th className="px-2 py-1.5 text-left">Ligne</th>
                              <th className="px-2 py-1.5 text-left">Company</th>
                              <th className="px-2 py-1.5 text-left">Thirdparty</th>
                              <th className="px-2 py-1.5 text-left">Famille_2</th>
                              <th className="px-2 py-1.5 text-left">Categorie_2</th>
                              {includeCategorie3 ? (
                                <th className="px-2 py-1.5 text-left">Categorie_3</th>
                              ) : null}
                              <th className="px-2 py-1.5 text-left">Date</th>
                              <th className="px-2 py-1.5 text-right">Amount</th>
                              <th className="px-2 py-1.5 text-left">Statut</th>
                            </tr>
                          </thead>
                          <tbody>
                            {previewRows.length === 0 ? (
                              <tr>
                                <td
                                  className="px-2 py-4 text-center text-[var(--text-muted)]"
                                  colSpan={includeCategorie3 ? 9 : 8}
                                >
                                  Aucune ligne à prévisualiser.
                                </td>
                              </tr>
                            ) : (
                              previewRows.map((row) => (
                                <tr
                                  key={row.rowIndex}
                                  className={`border-t border-[var(--border)] ${row.errors.length > 0 ? 'bg-red-50/40' : ''}`}
                                >
                                  <td className="px-2 py-1.5">{row.rowIndex}</td>
                                  <td className="px-2 py-1.5">{formatEntityName(row.company) || '—'}</td>
                                  <td className="px-2 py-1.5">{row.thirdparty || '—'}</td>
                                  <td className="px-2 py-1.5">{row.famille_2 || '—'}</td>
                                  <td className="px-2 py-1.5">{row.categorie_2 || '—'}</td>
                                  {includeCategorie3 ? (
                                    <td className="px-2 py-1.5">{row.categorie_3 || '—'}</td>
                                  ) : null}
                                  <td className="px-2 py-1.5">{row.month || '—'}</td>
                                  <td className="px-2 py-1.5 text-right">{row.amount}</td>
                                  <td className="px-2 py-1.5 text-[var(--text-muted)]">
                                    {row.errors.length > 0 ? row.errors.join(' · ') : 'OK'}
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                      {parsedRows.length > previewRows.length ? (
                        <p className="mt-2 text-xs text-[var(--text-muted)]">
                          Aperçu limité aux {previewRows.length} premières lignes.
                        </p>
                      ) : null}
                    </section>
                  </>
                ) : null}

                {importError ? <p className="text-sm text-red-500">{importError}</p> : null}
              </div>

              <footer className="flex items-center justify-end gap-2 border-t border-[var(--border)] px-4 py-3">
                <Button variant="ghost" className="!w-auto px-4" onPress={close} isDisabled={importing}>
                  Annuler
                </Button>
                <Button
                  className="!w-auto px-4"
                  onPress={() => void handleImport(close)}
                  isDisabled={
                    importing ||
                    validRows.length === 0 ||
                    missingMappings.length > 0 ||
                    !activeSheet
                  }
                >
                  {importing
                    ? 'Import en cours…'
                    : `Importer ${validRows.length} ligne(s)`}
                </Button>
              </footer>
            </>
          )}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
