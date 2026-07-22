import type { PageId, SectionProps } from '@/lib/types';
import { TreasurySection } from '@/components/dashboard/sections/TreasurySection';
import { InvoicesSection } from '@/components/dashboard/sections/InvoicesSection';
import { SupplierInvoicesSection } from '@/components/dashboard/sections/SupplierInvoicesSection';
import { PnlSection } from '@/components/dashboard/sections/PnlSection';
import { PnlAdjustmentsSection } from '@/components/dashboard/sections/PnlAdjustmentsSection';
import { PnlBudgetSection } from '@/components/dashboard/sections/PnlBudgetSection';
import {
  RefCategoriesSection,
  RefCustomersSection,
  RefSuppliersSection,
} from '@/components/dashboard/sections/ReferentialSections';
import { ThemeSection } from '@/components/dashboard/sections/ThemeSection';

export const SECTION_COMPONENTS: Record<
  Exclude<PageId, 'theme'>,
  React.ComponentType<SectionProps>
> = {
  treasury: TreasurySection,
  'customer-invoices': InvoicesSection,
  'supplier-invoices': SupplierInvoicesSection,
  pnl: PnlSection,
  'pnl-adjustments': PnlAdjustmentsSection,
  'pnl-budget': PnlBudgetSection,
  'ref-customers': RefCustomersSection,
  'ref-suppliers': RefSuppliersSection,
  'ref-categories': RefCategoriesSection,
};

export function isRegisteredPage(
  pageId: PageId,
): pageId is Exclude<PageId, 'theme'> {
  return pageId in SECTION_COMPONENTS;
}

/** @deprecated Theme uses a dedicated route; kept for tooling compatibility. */
export const SECTION_REGISTRY = {
  ...SECTION_COMPONENTS,
  theme: ThemeSection,
} as const;
