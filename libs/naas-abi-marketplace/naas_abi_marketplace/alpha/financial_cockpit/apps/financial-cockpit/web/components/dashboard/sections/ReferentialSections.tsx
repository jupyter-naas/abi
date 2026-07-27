import type { SectionProps } from '@/lib/types';
import { ReferentialTableSection } from '@/components/dashboard/sections/ReferentialTableSection';

export function RefCustomersSection(props: SectionProps) {
  return (
    <ReferentialTableSection
      {...props}
      kind="customers"
      title="Clients"
      hint="Référentiel clients consolidé (Pennylane) — utilisé pour valider les tiers dans les écritures budget et ajustements."
    />
  );
}

export function RefSuppliersSection(props: SectionProps) {
  return (
    <ReferentialTableSection
      {...props}
      kind="suppliers"
      title="Fournisseurs"
      hint="Référentiel fournisseurs consolidé — utilisé pour valider les tiers dans les écritures budget et ajustements."
    />
  );
}

export function RefCategoriesSection(props: SectionProps) {
  return (
    <ReferentialTableSection
      {...props}
      kind="categories"
      title="Catégories"
      hint="Référentiel familles / catégories Pennylane — utilisé pour valider Famille_2, Categorie_2 et Categorie_3."
    />
  );
}
