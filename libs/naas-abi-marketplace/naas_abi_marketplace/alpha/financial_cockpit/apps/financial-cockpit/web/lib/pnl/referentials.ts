import { accentFold } from '@/lib/pnl/model';

export type ReferentialCustomer = {
  organization_slug: string;
  company_name: string;
  customer_name: string;
  customer_vat_number: string;
  customer_billing_address_city: string;
  customer_emails: string;
};

export type ReferentialSupplier = {
  organization_slug: string;
  company_name: string;
  supplier_name: string;
  supplier_vat_number: string;
  supplier_postal_address_city: string;
};

export type ReferentialCategory = {
  organization_slug: string;
  company_name: string;
  category_group_label: string;
  category_label: string;
};

export type ReferentialsPayload = {
  customers: ReferentialCustomer[];
  suppliers: ReferentialSupplier[];
  categories: ReferentialCategory[];
};

export type ReferentialsIndex = {
  thirdpartyKeys: Set<string>;
  thirdpartyCanonical: Map<string, string>;
  familleKeys: Set<string>;
  familleCanonical: Map<string, string>;
  categorie2ByFamille: Map<string, Map<string, string>>;
  categorie3Keys: Set<string>;
  categorie3Canonical: Map<string, string>;
};

export type ReferentialEntryValues = {
  thirdparty?: string;
  famille_2?: string;
  categorie_2?: string;
  categorie_3?: string;
};

export type ReferentialValidationResult = {
  valid: boolean;
  errors: string[];
  normalized: ReferentialEntryValues;
};

function fold(value: string): string {
  return accentFold(value.trim());
}

function canonicalize(map: Map<string, string>, raw: string): string {
  const key = fold(raw);
  return map.get(key) ?? raw.trim();
}

export function buildReferentialsIndex(payload: ReferentialsPayload): ReferentialsIndex {
  const thirdpartyKeys = new Set<string>();
  const thirdpartyCanonical = new Map<string, string>();
  const familleKeys = new Set<string>();
  const familleCanonical = new Map<string, string>();
  const categorie2ByFamille = new Map<string, Map<string, string>>();
  const categorie3Keys = new Set<string>();
  const categorie3Canonical = new Map<string, string>();

  for (const row of payload.customers) {
    const name = row.customer_name.trim();
    if (!name) {
      continue;
    }
    const key = fold(name);
    thirdpartyKeys.add(key);
    thirdpartyCanonical.set(key, name);
  }

  for (const row of payload.suppliers) {
    const name = row.supplier_name.trim();
    if (!name) {
      continue;
    }
    const key = fold(name);
    thirdpartyKeys.add(key);
    thirdpartyCanonical.set(key, name);
  }

  for (const row of payload.categories) {
    const famille = row.category_group_label.trim();
    const categorie2 = row.category_label.trim();
    if (!famille) {
      continue;
    }

    const familleKey = fold(famille);
    familleKeys.add(familleKey);
    familleCanonical.set(familleKey, famille);

    if (!categorie2) {
      continue;
    }

    let byFamille = categorie2ByFamille.get(familleKey);
    if (!byFamille) {
      byFamille = new Map<string, string>();
      categorie2ByFamille.set(familleKey, byFamille);
    }
    const categorie2Key = fold(categorie2);
    byFamille.set(categorie2Key, categorie2);

    categorie3Keys.add(categorie2Key);
    categorie3Canonical.set(categorie2Key, categorie2);
  }

  return {
    thirdpartyKeys,
    thirdpartyCanonical,
    familleKeys,
    familleCanonical,
    categorie2ByFamille,
    categorie3Keys,
    categorie3Canonical,
  };
}

export function validateReferentialEntry(
  index: ReferentialsIndex,
  values: ReferentialEntryValues,
): ReferentialValidationResult {
  const errors: string[] = [];
  const normalized: ReferentialEntryValues = {};

  const thirdparty = values.thirdparty?.trim() ?? '';
  if (thirdparty) {
    const key = fold(thirdparty);
    if (!index.thirdpartyKeys.has(key)) {
      errors.push('Thirdparty inconnu (absent des référentiels Clients et Fournisseurs)');
    } else {
      normalized.thirdparty = index.thirdpartyCanonical.get(key) ?? thirdparty;
    }
  }

  const famille = values.famille_2?.trim() ?? '';
  if (famille) {
    const familleKey = fold(famille);
    if (!index.familleKeys.has(familleKey)) {
      errors.push('Famille_2 inconnue (absente du référentiel Catégories)');
    } else {
      normalized.famille_2 = index.familleCanonical.get(familleKey) ?? famille;
    }
  }

  const categorie2 = values.categorie_2?.trim() ?? '';
  if (categorie2) {
    const familleKey = fold(normalized.famille_2 ?? famille);
    const byFamille = index.categorie2ByFamille.get(familleKey);
    const categorie2Key = fold(categorie2);
    if (!byFamille?.has(categorie2Key)) {
      errors.push('Categorie_2 inconnue pour cette Famille_2');
    } else {
      normalized.categorie_2 = byFamille.get(categorie2Key) ?? categorie2;
    }
  }

  const categorie3 = values.categorie_3?.trim() ?? '';
  if (categorie3) {
    const categorie3Key = fold(categorie3);
    if (!index.categorie3Keys.has(categorie3Key)) {
      errors.push('Categorie_3 inconnue (absente du référentiel Catégories)');
    } else {
      normalized.categorie_3 = index.categorie3Canonical.get(categorie3Key) ?? categorie3;
    }
  }

  return { valid: errors.length === 0, errors, normalized };
}

export function referentialFamilleOptions(index: ReferentialsIndex): string[] {
  return [...index.familleCanonical.values()].sort((a, b) => a.localeCompare(b, 'fr'));
}

export function referentialCategorie2Options(
  index: ReferentialsIndex,
  famille: string,
): string[] {
  const byFamille = index.categorie2ByFamille.get(fold(famille));
  if (!byFamille) {
    return [];
  }
  return [...byFamille.values()].sort((a, b) => a.localeCompare(b, 'fr'));
}

export function referentialThirdpartyOptions(index: ReferentialsIndex): string[] {
  return [...index.thirdpartyCanonical.values()].sort((a, b) => a.localeCompare(b, 'fr'));
}
