import type { PageId, SectionProps } from '@/lib/types';
import { DashboardSection } from '@/components/dashboard/sections/DashboardSection';
import { TreasurySection } from '@/components/dashboard/sections/TreasurySection';
import { CashPositionSection } from '@/components/dashboard/sections/CashPositionSection';
import { FinancingSection } from '@/components/dashboard/sections/FinancingSection';
import { InvoicesSection } from '@/components/dashboard/sections/InvoicesSection';
import { SupplierInvoicesSection } from '@/components/dashboard/sections/SupplierInvoicesSection';
import { PnlSection } from '@/components/dashboard/sections/PnlSection';
import { BalanceSheetSection } from '@/components/dashboard/sections/BalanceSheetSection';
import { CashFlowSection } from '@/components/dashboard/sections/CashFlowSection';
import { FinancialRatiosSection } from '@/components/dashboard/sections/FinancialRatiosSection';
import { PnlAdjustmentsSection } from '@/components/dashboard/sections/PnlAdjustmentsSection';
import { PnlBudgetSection } from '@/components/dashboard/sections/PnlBudgetSection';
import { ForecastSection } from '@/components/dashboard/sections/ForecastSection';
import { ScenarioAnalysisSection } from '@/components/dashboard/sections/ScenarioAnalysisSection';
import { CostCentersSection } from '@/components/dashboard/sections/CostCentersSection';
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
  dashboard: DashboardSection,
  'cash-position': CashPositionSection,
  treasury: TreasurySection,
  financing: FinancingSection,
  'customer-invoices': InvoicesSection,
  'supplier-invoices': SupplierInvoicesSection,
  pnl: PnlSection,
  'balance-sheet': BalanceSheetSection,
  'cash-flow': CashFlowSection,
  'financial-ratios': FinancialRatiosSection,
  'pnl-adjustments': PnlAdjustmentsSection,
  'pnl-budget': PnlBudgetSection,
  forecast: ForecastSection,
  'scenario-analysis': ScenarioAnalysisSection,
  'cost-centers': CostCentersSection,
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
