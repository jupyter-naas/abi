const PENNYLANE_APP_BASE = 'https://app.pennylane.com';

export const PENNYLANE_LINK_TITLE =
  'Ouvre Pennylane dans un nouvel onglet. Une connexion Pennylane est nécessaire pour accéder aux données.';

export function buildPennylaneCustomerInvoicesSearchUrl(
  companyId: number | string,
  invoiceNumber: string,
): string {
  const filters = [
    {
      field: 'invoice_number',
      operator: 'search_all',
      value: invoiceNumber,
    },
  ];
  const filterParam = encodeURIComponent(JSON.stringify(filters));
  return (
    `${PENNYLANE_APP_BASE}/companies/${companyId}/clients/customer_invoices` +
    `?filter=${filterParam}&page=1&sort=-date%2C-id&subtab=all`
  );
}

export function resolvePennylaneTransactionsUrl(
  record: {
    pennylane_transactions_url?: string | null;
    pennylane_company_id?: number | null;
    invoice_ref?: string | null;
  },
): string | null {
  if (record.pennylane_transactions_url) {
    return record.pennylane_transactions_url;
  }
  const companyId = record.pennylane_company_id;
  const invoiceRef = record.invoice_ref?.trim();
  if (!companyId || !invoiceRef) {
    return null;
  }
  return buildPennylaneCustomerInvoicesSearchUrl(companyId, invoiceRef);
}
