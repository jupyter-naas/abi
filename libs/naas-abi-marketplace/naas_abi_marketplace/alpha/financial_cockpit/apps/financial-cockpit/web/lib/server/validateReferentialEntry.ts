import 'server-only';

import { buildReferentialsIndex, validateReferentialEntry } from '@/lib/pnl/referentials';
import { listReferentials } from '@/lib/server/referentialsStore';

export async function validatePnlEntryReferentials(
  input: {
    thirdparty?: string;
    famille_2?: string;
    categorie_2?: string;
    categorie_3?: string;
  },
  organizationSlugs?: ReadonlySet<string>,
): Promise<{ ok: true; normalized: typeof input } | { ok: false; errors: string[] }> {
  const payload = await listReferentials(organizationSlugs);
  const index = buildReferentialsIndex(payload);
  const result = validateReferentialEntry(index, input);
  if (!result.valid) {
    return { ok: false, errors: result.errors };
  }
  return { ok: true, normalized: { ...input, ...result.normalized } };
}
