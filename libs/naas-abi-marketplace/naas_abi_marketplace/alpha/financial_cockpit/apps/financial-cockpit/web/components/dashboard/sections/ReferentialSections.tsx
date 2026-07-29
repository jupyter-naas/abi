import type { SectionProps } from '@/lib/types';
import { ReferentialTableSection } from '@/components/dashboard/sections/ReferentialTableSection';

export function RefCustomersSection(props: SectionProps) {
  return (
    <ReferentialTableSection
      {...props}
      kind="customers"
      title="Customers"
      hint="Consolidated customer reference data (Pennylane) — used to validate thirdparties in the budget and adjustment entries."
    />
  );
}

export function RefSuppliersSection(props: SectionProps) {
  return (
    <ReferentialTableSection
      {...props}
      kind="suppliers"
      title="Suppliers"
      hint="Consolidated supplier reference data — used to validate thirdparties in the budget and adjustment entries."
    />
  );
}

export function RefCategoriesSection(props: SectionProps) {
  return (
    <ReferentialTableSection
      {...props}
      kind="categories"
      title="Categories"
      hint="Pennylane famille / category reference data — used to validate Famille_2, Categorie_2 and Categorie_3."
    />
  );
}
