import 'server-only';

import {
  deleteDataFile,
  listDataFiles,
  readJsonFile,
  writeJsonFile,
} from '@/lib/data/storage';
import type { EntityId } from '@/lib/types';

/** User-entered follow-up data attached to an unpaid invoice. */
export type InvoiceAnnotation = {
  invoice_number: string;
  status_relance: string;
  date_relance: string;
  notes: string;
  date_edited: string;
};

export type InvoiceAnnotationInput = Pick<
  InvoiceAnnotation,
  'invoice_number' | 'status_relance' | 'date_relance' | 'notes'
>;

export const INVOICE_ANNOTATION_FIELDS = ['date_relance', 'notes'] as const;

export type InvoiceAnnotationField = (typeof INVOICE_ANNOTATION_FIELDS)[number];

/** One edit event = one JSON file in the global follow-up folder. */
export type InvoiceAnnotationLogRecord = {
  event_id: string;
  entity_id: string;
  company: string;
  organization_slug: string;
  site: string;
  client: string;
  categorie_2: string;
  invoice_number: string;
  status_relance: string;
  field: InvoiceAnnotationField;
  value: string;
  user: string;
  date_edited: string;
};

/** Where the edited invoice belongs — recorded on each event for cross-perimeter display/filtering. */
export type InvoiceAnnotationSource = {
  company: string;
  organization_slug: string;
  site: string;
  client: string;
  categorie_2: string;
};

/**
 * Follow-up is keyed by invoice, not by entity: an edit made on a
 * consolidation view must be visible on the organization view (and any other
 * consolidation containing that invoice). Events are therefore stored in one
 * global folder and the current values are recomputed by folding the events
 * chronologically — the event files are the single source of truth.
 */
const EVENTS_FOLDER = 'globals/follow_up_unpaid';

/**
 * Every event is mirrored here at write time. The app never displays, edits,
 * or deletes backup files — they only feed admin-triggered restores.
 */
const BACKUP_FOLDER = `${EVENTS_FOLDER}/backup`;

export function invoiceAnnotationKey(
  invoiceNumber: string,
  statusRelance: string,
): string {
  return `${invoiceNumber}::${statusRelance}`;
}

function isAnnotationField(value: unknown): value is InvoiceAnnotationField {
  return (
    typeof value === 'string' &&
    (INVOICE_ANNOTATION_FIELDS as readonly string[]).includes(value)
  );
}

function parseLogRecord(
  entry: Record<string, unknown> | null,
): InvoiceAnnotationLogRecord | null {
  if (
    !entry ||
    typeof entry.invoice_number !== 'string' ||
    !entry.invoice_number ||
    !isAnnotationField(entry.field)
  ) {
    return null;
  }
  return {
    event_id: typeof entry.event_id === 'string' ? entry.event_id : '',
    entity_id: typeof entry.entity_id === 'string' ? entry.entity_id : '',
    company: typeof entry.company === 'string' ? entry.company : '',
    organization_slug:
      typeof entry.organization_slug === 'string' ? entry.organization_slug : '',
    site: typeof entry.site === 'string' ? entry.site : '',
    client: typeof entry.client === 'string' ? entry.client : '',
    categorie_2: typeof entry.categorie_2 === 'string' ? entry.categorie_2 : '',
    invoice_number: entry.invoice_number,
    status_relance:
      typeof entry.status_relance === 'string' ? entry.status_relance : '',
    field: entry.field,
    value: typeof entry.value === 'string' ? entry.value : '',
    user: typeof entry.user === 'string' ? entry.user : '',
    date_edited: typeof entry.date_edited === 'string' ? entry.date_edited : '',
  };
}

function eventFileName(entry: InvoiceAnnotationLogRecord): string {
  return `${entry.date_edited.replace(/[:.]/g, '-')}_${entry.field}_${entry.event_id}.json`;
}

function eventFileKey(entry: InvoiceAnnotationLogRecord): string {
  return `${EVENTS_FOLDER}/${eventFileName(entry)}`;
}

/**
 * Event files written before event_id existed in the payload still carry the
 * uuid in their filename ({timestamp}_{field}_{uuid}.json) — recover it so
 * those rows stay editable and deletable.
 */
function eventIdFromKey(key: string): string {
  const base = key.slice(key.lastIndexOf('/') + 1).replace(/\.json$/, '');
  const lastUnderscore = base.lastIndexOf('_');
  return lastUnderscore >= 0 ? base.slice(lastUnderscore + 1) : base;
}

async function listEventKeys(): Promise<string[]> {
  // Only direct children count as events. Subfolders (e.g. backup/) are
  // invisible to the app: never displayed, never edited, never deleted.
  const prefix = `${EVENTS_FOLDER}/`;
  return (await listDataFiles(EVENTS_FOLDER)).filter(
    (key) => key.endsWith('.json') && !key.slice(prefix.length).includes('/'),
  );
}

/** Concatenate every event file in the global folder into one chronological log. */
export async function loadInvoiceAnnotationEvents(): Promise<
  InvoiceAnnotationLogRecord[]
> {
  const keys = await listEventKeys();
  const files = await Promise.all(
    keys.map(async (key) => ({
      key,
      entry: parseLogRecord(await readJsonFile<Record<string, unknown>>(key)),
    })),
  );
  return files
    .filter(
      (file): file is { key: string; entry: InvoiceAnnotationLogRecord } =>
        file.entry !== null,
    )
    .map(({ key, entry }) =>
      entry.event_id ? entry : { ...entry, event_id: eventIdFromKey(key) },
    )
    .sort((a, b) => (a.date_edited < b.date_edited ? -1 : 1));
}

/** Fold events into the latest value per invoice + statut relance + field. */
function foldEvents(
  events: InvoiceAnnotationLogRecord[],
): Map<string, InvoiceAnnotation> {
  const byKey = new Map<string, InvoiceAnnotation>();
  for (const event of events) {
    const key = invoiceAnnotationKey(event.invoice_number, event.status_relance);
    const current = byKey.get(key) ?? {
      invoice_number: event.invoice_number,
      status_relance: event.status_relance,
      date_relance: '',
      notes: '',
      date_edited: '',
    };
    byKey.set(key, {
      ...current,
      [event.field]: event.value,
      date_edited: event.date_edited,
    });
  }
  return byKey;
}

export async function loadInvoiceAnnotations(): Promise<{
  records: InvoiceAnnotation[];
  history: InvoiceAnnotationLogRecord[];
}> {
  const history = await loadInvoiceAnnotationEvents();
  const records = [...foldEvents(history).values()].filter(
    (record) => record.date_relance.trim() || record.notes.trim(),
  );
  return { records, history };
}

export async function upsertInvoiceAnnotation(
  entityId: EntityId,
  input: InvoiceAnnotationInput,
  source: InvoiceAnnotationSource,
  user: string,
): Promise<{ record: InvoiceAnnotation; logEntries: InvoiceAnnotationLogRecord[] }> {
  const annotation: InvoiceAnnotation = {
    ...input,
    date_edited: new Date().toISOString(),
  };

  const events = await loadInvoiceAnnotationEvents();
  const previous = foldEvents(events).get(
    invoiceAnnotationKey(input.invoice_number, input.status_relance),
  );

  const logEntries: InvoiceAnnotationLogRecord[] = INVOICE_ANNOTATION_FIELDS.filter(
    (field) => (previous?.[field] ?? '') !== annotation[field],
  ).map((field) => ({
    event_id: crypto.randomUUID(),
    entity_id: entityId,
    company: source.company,
    organization_slug: source.organization_slug,
    site: source.site,
    client: source.client,
    categorie_2: source.categorie_2,
    invoice_number: annotation.invoice_number,
    status_relance: annotation.status_relance,
    field,
    value: annotation[field],
    user,
    date_edited: annotation.date_edited,
  }));

  for (const entry of logEntries) {
    const written = await writeJsonFile(eventFileKey(entry), entry);
    if (!written) {
      throw new Error('Failed to persist invoice annotation event');
    }
    const backedUp = await writeJsonFile(
      `${BACKUP_FOLDER}/${eventFileName(entry)}`,
      entry,
    );
    if (!backedUp) {
      throw new Error('Failed to back up invoice annotation event');
    }
  }

  return { record: annotation, logEntries };
}

async function findEventKey(eventId: string): Promise<string | null> {
  if (!eventId) {
    return null;
  }
  const keys = await listEventKeys();
  return keys.find((key) => key.includes(eventId)) ?? null;
}

/** Update the value of one log event in place (audit timestamp is preserved). */
export async function updateInvoiceAnnotationEvent(
  eventId: string,
  value: string,
  user: string,
): Promise<InvoiceAnnotationLogRecord | null> {
  const key = await findEventKey(eventId);
  if (!key) {
    return null;
  }
  const entry = parseLogRecord(await readJsonFile<Record<string, unknown>>(key));
  if (!entry) {
    return null;
  }
  const updated: InvoiceAnnotationLogRecord = {
    ...entry,
    event_id: entry.event_id || eventIdFromKey(key),
    value,
    user,
  };
  const written = await writeJsonFile(key, updated);
  if (!written) {
    throw new Error('Failed to update invoice annotation event');
  }
  return updated;
}

/**
 * Copy backed-up events into the live folder (admin restore). Optionally only
 * events with `date_edited >= fromIso`. Existing live events are never
 * overwritten and the backup itself is never modified. Returns the number of
 * events restored.
 */
export async function restoreInvoiceAnnotationEvents(
  fromIso?: string,
): Promise<number> {
  const backupPrefix = `${BACKUP_FOLDER}/`;
  const backupKeys = (await listDataFiles(BACKUP_FOLDER)).filter(
    (key) => key.endsWith('.json') && !key.slice(backupPrefix.length).includes('/'),
  );
  const liveNames = new Set(
    (await listEventKeys()).map((key) => key.slice(key.lastIndexOf('/') + 1)),
  );

  let restored = 0;
  for (const key of backupKeys) {
    const name = key.slice(key.lastIndexOf('/') + 1);
    if (liveNames.has(name)) {
      continue;
    }
    const entry = parseLogRecord(await readJsonFile<Record<string, unknown>>(key));
    if (!entry || (fromIso && entry.date_edited < fromIso)) {
      continue;
    }
    const record = entry.event_id
      ? entry
      : { ...entry, event_id: eventIdFromKey(key) };
    if (await writeJsonFile(`${EVENTS_FOLDER}/${name}`, record)) {
      restored += 1;
    }
  }
  return restored;
}

/** Delete log events by id; returns the number of files actually removed. */
export async function deleteInvoiceAnnotationEvents(
  eventIds: string[],
): Promise<number> {
  const ids = eventIds.filter((id) => id.trim());
  if (ids.length === 0) {
    return 0;
  }
  const keys = await listEventKeys();
  let deleted = 0;
  for (const id of ids) {
    const key = keys.find((candidate) => candidate.includes(id));
    if (key && (await deleteDataFile(key))) {
      deleted += 1;
    }
  }
  return deleted;
}
