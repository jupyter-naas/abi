import type { CompanyConfig, EntityConfig } from '@/lib/types';
import { isConsolidation } from '@/lib/config/entityHelpers';

/**
 * Organization slugs (or the entity's own id for a plain organization) that
 * adjustment / budget rows must match to be visible on the current view.
 */
export function perimeterSlugsFor(
  entity: EntityConfig,
  company: CompanyConfig | null,
): Set<string> {
  if (company) {
    return new Set([company.organization_slug]);
  }
  if (isConsolidation(entity)) {
    const slugs = (entity.companies ?? []).map((c) => c.organization_slug);
    return new Set(slugs.length > 0 ? slugs : [entity.entity_id]);
  }
  // Plain organization entities record their own slug as entity_id/organization_slug.
  return new Set([entity.entity_id]);
}

export type OrganizationOption = { slug: string; label: string };

/** Organizations selectable in the adjustment/budget editors for the current view. */
export function organizationOptionsFor(
  entity: EntityConfig,
  company: CompanyConfig | null,
): OrganizationOption[] {
  if (company) {
    return [{ slug: company.organization_slug, label: company.display_name }];
  }
  if (isConsolidation(entity)) {
    const companies = entity.companies ?? [];
    if (companies.length > 0) {
      return companies.map((c) => ({ slug: c.organization_slug, label: c.display_name }));
    }
    return [{ slug: entity.entity_id, label: entity.display_name }];
  }
  return [{ slug: entity.entity_id, label: entity.display_name }];
}
