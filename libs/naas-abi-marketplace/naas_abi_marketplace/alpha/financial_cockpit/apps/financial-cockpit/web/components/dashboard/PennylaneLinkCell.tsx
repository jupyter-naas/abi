'use client';

import { PENNYLANE_LINK_TITLE, resolvePennylaneTransactionsUrl } from '@/lib/pennylaneUrls';

type PennylaneLinkCellProps = {
  pennylaneTransactionsUrl?: string | null;
  pennylaneCompanyId?: number | null;
  invoiceRef?: string | null;
};

export function PennylaneLinkCell({
  pennylaneTransactionsUrl,
  pennylaneCompanyId,
  invoiceRef,
}: PennylaneLinkCellProps) {
  const pennylaneUrl = resolvePennylaneTransactionsUrl({
    pennylane_transactions_url: pennylaneTransactionsUrl,
    pennylane_company_id: pennylaneCompanyId,
    invoice_ref: invoiceRef,
  });

  return (
    <div className="flex items-center gap-1.5">
      {pennylaneUrl ? (
        <a
          href={pennylaneUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--secondary)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--secondary)]"
          aria-label="Ouvrir dans Pennylane (connexion requise)"
          title={PENNYLANE_LINK_TITLE}
        >
          <PennylaneIcon />
        </a>
      ) : (
        <span className="text-[var(--text-muted)] opacity-60">—</span>
      )}
    </div>
  );
}

function PennylaneIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M11.25 3.5H6.75A2.25 2.25 0 0 0 4.5 5.75v8.5A2.25 2.25 0 0 0 6.75 16.5h6.5A2.25 2.25 0 0 0 15.5 14.25V8.75M11.25 3.5 15.5 7.75M11.25 3.5V7.75H15.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
