import { accentFold, PNL_FAMILLES } from '@/lib/pnl/model';
import type { OrganizationOption } from '@/lib/pnl/perimeter';
import {
  type ReferentialsIndex,
  validateReferentialEntry,
} from '@/lib/pnl/referentials';

export type PnlEntryImportField =
  | 'company'
  | 'thirdparty'
  | 'famille_2'
  | 'categorie_2'
  | 'categorie_3'
  | 'month'
  | 'amount';

export type PnlEntryImportFieldSpec = {
  key: PnlEntryImportField;
  label: string;
  required: boolean;
};

export type PnlEntryColumnMapping = Partial<Record<PnlEntryImportField, string>>;

export type ParsedPnlImportRow = {
  rowIndex: number;
  organization_slug: string;
  company: string;
  famille_2: string;
  categorie_2: string;
  categorie_3: string;
  thirdparty: string;
  month: string;
  amount: number;
  errors: string[];
};

const FIELD_ALIASES: Record<PnlEntryImportField, readonly string[]> = {
  company: ['company', 'societe', 'société', 'organisation', 'organization', 'entite', 'entité', 'source'],
  thirdparty: [
    'thirdparty',
    'third party',
    'third_party',
    'tiers',
    'partenaire',
    'fournisseur',
    'client',
  ],
  famille_2: ['famille_2', 'famille 2', 'famille2', 'famille'],
  categorie_2: ['categorie_2', 'catégorie 2', 'categorie2', 'categorie', 'catégorie'],
  categorie_3: ['categorie_3', 'catégorie 3', 'categorie3'],
  month: ['month', 'date', 'mois', 'periode', 'période', 'periode comptable'],
  amount: ['amount', 'montant', 'valeur', 'solde'],
};

function normalizeHeader(value: string): string {
  return accentFold(value).replace(/[_-]+/g, ' ');
}

export function pnlEntryImportFields(includeCategorie3: boolean): PnlEntryImportFieldSpec[] {
  const fields: PnlEntryImportFieldSpec[] = [
    { key: 'company', label: 'Company', required: false },
    { key: 'thirdparty', label: 'Thirdparty', required: false },
    { key: 'famille_2', label: 'Famille_2', required: true },
    { key: 'categorie_2', label: 'Categorie_2', required: false },
    { key: 'month', label: 'Date (YYYY-MM)', required: true },
    { key: 'amount', label: 'Amount', required: true },
  ];
  if (includeCategorie3) {
    fields.splice(4, 0, { key: 'categorie_3', label: 'Categorie_3', required: false });
  }
  return fields;
}

export function guessPnlEntryColumnMapping(headers: string[]): PnlEntryColumnMapping {
  const mapping: PnlEntryColumnMapping = {};
  const normalizedHeaders = headers.map((header) => ({
    header,
    key: normalizeHeader(header),
  }));

  for (const field of Object.keys(FIELD_ALIASES) as PnlEntryImportField[]) {
    const aliases = FIELD_ALIASES[field].map(normalizeHeader);
    const exact = normalizedHeaders.find((entry) => aliases.includes(entry.key));
    if (exact) {
      mapping[field] = exact.header;
      continue;
    }
    const partial = normalizedHeaders.find((entry) =>
      aliases.some((alias) => entry.key.includes(alias) || alias.includes(entry.key)),
    );
    if (partial) {
      mapping[field] = partial.header;
    }
  }

  return mapping;
}

export function parseMonthValue(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) {
    return null;
  }
  if (/^\d{4}-\d{2}$/.test(trimmed)) {
    return trimmed;
  }
  const isoDay = /^(\d{4})-(\d{2})-\d{2}$/.exec(trimmed);
  if (isoDay) {
    return `${isoDay[1]}-${isoDay[2]}`;
  }
  const slash = /^(\d{1,2})[/.-](\d{4})$/.exec(trimmed);
  if (slash) {
    return `${slash[2]}-${slash[1].padStart(2, '0')}`;
  }
  const reverse = /^(\d{4})[/.-](\d{1,2})$/.exec(trimmed);
  if (reverse) {
    return `${reverse[1]}-${reverse[2].padStart(2, '0')}`;
  }
  const parsed = new Date(trimmed);
  if (!Number.isNaN(parsed.getTime())) {
    return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}`;
  }
  return null;
}

export function parseAmountValue(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) {
    return null;
  }
  let normalized = trimmed.replace(/\s/g, '').replace(/[€$£]/g, '');
  if (normalized.includes(',') && normalized.includes('.')) {
    normalized = normalized.replace(/\./g, '').replace(',', '.');
  } else {
    normalized = normalized.replace(',', '.');
  }
  const amount = Number(normalized);
  return Number.isFinite(amount) ? amount : null;
}

export function resolveFamilleValue(raw: string, index?: ReferentialsIndex | null): string | null {
  const folded = accentFold(raw);
  if (!folded) {
    return null;
  }

  if (index) {
    if (index.familleKeys.has(folded)) {
      return index.familleCanonical.get(folded) ?? raw.trim();
    }
    for (const key of index.familleKeys) {
      if (key.includes(folded) || folded.includes(key)) {
        return index.familleCanonical.get(key) ?? raw.trim();
      }
    }
  }

  for (const famille of PNL_FAMILLES) {
    if (accentFold(famille.value) === folded) {
      return famille.value;
    }
  }
  for (const famille of PNL_FAMILLES) {
    const candidate = accentFold(famille.value);
    if (candidate.includes(folded) || folded.includes(candidate)) {
      return famille.value;
    }
  }
  return null;
}

export function resolveOrganizationOption(
  raw: string,
  orgOptions: OrganizationOption[],
  defaultSlug?: string,
): OrganizationOption | null {
  if (orgOptions.length === 1) {
    return orgOptions[0];
  }
  const folded = accentFold(raw);
  if (!folded && defaultSlug) {
    return orgOptions.find((option) => option.slug === defaultSlug) ?? null;
  }
  for (const option of orgOptions) {
    if (accentFold(option.label) === folded || accentFold(option.slug) === folded) {
      return option;
    }
  }
  for (const option of orgOptions) {
    const label = accentFold(option.label);
    if (label.includes(folded) || folded.includes(label)) {
      return option;
    }
  }
  if (defaultSlug) {
    return orgOptions.find((option) => option.slug === defaultSlug) ?? null;
  }
  return null;
}

function readMappedValue(
  row: Record<string, string>,
  mapping: PnlEntryColumnMapping,
  field: PnlEntryImportField,
): string {
  const header = mapping[field];
  return header ? (row[header] ?? '').trim() : '';
}

export function parsePnlImportRows(
  rows: Record<string, string>[],
  mapping: PnlEntryColumnMapping,
  orgOptions: OrganizationOption[],
  options: {
    includeCategorie3: boolean;
    defaultOrganizationSlug?: string;
    referentialsIndex?: ReferentialsIndex | null;
  },
): ParsedPnlImportRow[] {
  const fields = pnlEntryImportFields(options.includeCategorie3);

  return rows.map((row, index) => {
    const errors: string[] = [];
    const rowIndex = index + 2;

    const companyRaw = readMappedValue(row, mapping, 'company');
    const organization = resolveOrganizationOption(
      companyRaw,
      orgOptions,
      options.defaultOrganizationSlug,
    );
    if (!organization) {
      errors.push(
        orgOptions.length > 1
          ? 'Company introuvable dans le périmètre'
          : 'Company requise pour ce périmètre',
      );
    }

    const familleRaw = readMappedValue(row, mapping, 'famille_2');
    const famille = resolveFamilleValue(familleRaw, options.referentialsIndex);
    if (!famille) {
      errors.push('Famille_2 invalide ou manquante');
    }

    const monthRaw = readMappedValue(row, mapping, 'month');
    const month = parseMonthValue(monthRaw);
    if (!month) {
      errors.push('Date invalide (attendu YYYY-MM)');
    }

    const amountRaw = readMappedValue(row, mapping, 'amount');
    const amount = parseAmountValue(amountRaw);
    if (amount === null) {
      errors.push('Amount invalide ou manquant');
    }

    const thirdparty = readMappedValue(row, mapping, 'thirdparty');
    const categorie_2 = readMappedValue(row, mapping, 'categorie_2');
    const categorie_3 = options.includeCategorie3
      ? readMappedValue(row, mapping, 'categorie_3')
      : '';

    if (options.referentialsIndex) {
      const referential = validateReferentialEntry(options.referentialsIndex, {
        thirdparty,
        famille_2: famille ?? familleRaw,
        categorie_2,
        categorie_3,
      });
      errors.push(...referential.errors);
    }

    for (const field of fields) {
      if (!field.required) {
        continue;
      }
      if (field.key === 'company' && orgOptions.length === 1) {
        continue;
      }
      if (field.key === 'famille_2' || field.key === 'month' || field.key === 'amount') {
        continue;
      }
      if (!mapping[field.key]) {
        errors.push(`Colonne ${field.label} non mappée`);
      }
    }

    const isEmpty = fields.every((field) => !readMappedValue(row, mapping, field.key));
    if (isEmpty) {
      errors.push('Ligne vide');
    }

    const referentialNormalized = options.referentialsIndex
      ? validateReferentialEntry(options.referentialsIndex, {
          thirdparty,
          famille_2: famille ?? familleRaw,
          categorie_2,
          categorie_3,
        }).normalized
      : {};

    return {
      rowIndex,
      organization_slug: organization?.slug ?? '',
      company: organization?.label ?? companyRaw,
      famille_2: referentialNormalized.famille_2 ?? famille ?? familleRaw,
      categorie_2: referentialNormalized.categorie_2 ?? categorie_2,
      categorie_3: referentialNormalized.categorie_3 ?? categorie_3,
      thirdparty: referentialNormalized.thirdparty ?? thirdparty,
      month: month ?? monthRaw,
      amount: amount ?? 0,
      errors,
    };
  });
}

export function validPnlImportRows(rows: ParsedPnlImportRow[]): ParsedPnlImportRow[] {
  return rows.filter((row) => row.errors.length === 0);
}

export function missingRequiredMappings(
  mapping: PnlEntryColumnMapping,
  orgOptions: OrganizationOption[],
  includeCategorie3: boolean,
): string[] {
  const missing: string[] = [];
  const fields = pnlEntryImportFields(includeCategorie3);
  for (const field of fields) {
    if (!field.required) {
      continue;
    }
    if (field.key === 'company' && orgOptions.length === 1) {
      continue;
    }
    if (!mapping[field.key]) {
      missing.push(field.label);
    }
  }
  return missing;
}
