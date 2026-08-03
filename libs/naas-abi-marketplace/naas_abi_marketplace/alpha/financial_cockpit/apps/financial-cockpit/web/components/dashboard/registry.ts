import type { PageId, SectionProps } from '@/lib/types';
import { DashboardSection } from '@/components/dashboard/dashboard/DashboardSection';
import { TreasurySection } from '@/components/dashboard/treasury/cash-forecast/TreasurySection';
import { CashPositionSection } from '@/components/dashboard/treasury/cash-position/CashPositionSection';
import { FinancingSection } from '@/components/dashboard/treasury/financing/FinancingSection';
import { CustomersSection } from '@/components/dashboard/operations/customer-invoices/CustomersSection';
import { SuppliersSection } from '@/components/dashboard/operations/supplier-invoices/SuppliersSection';
import { ExpensesSection } from '@/components/dashboard/operations/expenses/ExpensesSection';
import { ProcurementSection } from '@/components/dashboard/operations/procurement/ProcurementSection';
import { PnlSection } from '@/components/dashboard/performance/income-statement/PnlSection';
import { BalanceSheetSection } from '@/components/dashboard/performance/balance-sheet/BalanceSheetSection';
import { CashFlowSection } from '@/components/dashboard/performance/cash-flow/CashFlowSection';
import { FinancialRatiosSection } from '@/components/dashboard/performance/financial-ratios/FinancialRatiosSection';
import { PnlAdjustmentsSection } from '@/components/dashboard/comptabilite/adjustment-entries/PnlAdjustmentsSection';
import { PnlBudgetSection } from '@/components/dashboard/pilotage/budget/PnlBudgetSection';
import { ForecastSection } from '@/components/dashboard/pilotage/forecast/ForecastSection';
import { ScenarioAnalysisSection } from '@/components/dashboard/pilotage/scenario-analysis/ScenarioAnalysisSection';
import { CostCentersSection } from '@/components/dashboard/pilotage/cost-centers/CostCentersSection';
import { GeneralLedgerSection } from '@/components/dashboard/comptabilite/general-ledger/GeneralLedgerSection';
import { JournalEntriesSection } from '@/components/dashboard/comptabilite/journal-entries/JournalEntriesSection';
import { FixedAssetsSection } from '@/components/dashboard/comptabilite/fixed-assets/FixedAssetsSection';
import { FinancialCloseSection } from '@/components/dashboard/comptabilite/financial-close/FinancialCloseSection';
import { ThemeSection } from '@/components/dashboard/theme/ThemeSection';

export const SECTION_COMPONENTS: Record<
  Exclude<PageId, 'theme'>,
  React.ComponentType<SectionProps>
> = {
  dashboard: DashboardSection,
  'cash-position': CashPositionSection,
  treasury: TreasurySection,
  financing: FinancingSection,
  'customer-invoices': CustomersSection,
  'supplier-invoices': SuppliersSection,
  expenses: ExpensesSection,
  procurement: ProcurementSection,
  pnl: PnlSection,
  'balance-sheet': BalanceSheetSection,
  'cash-flow': CashFlowSection,
  'financial-ratios': FinancialRatiosSection,
  'pnl-adjustments': PnlAdjustmentsSection,
  'pnl-budget': PnlBudgetSection,
  forecast: ForecastSection,
  'scenario-analysis': ScenarioAnalysisSection,
  'cost-centers': CostCentersSection,
  'general-ledger': GeneralLedgerSection,
  'journal-entries': JournalEntriesSection,
  'fixed-assets': FixedAssetsSection,
  'financial-close': FinancialCloseSection,
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
