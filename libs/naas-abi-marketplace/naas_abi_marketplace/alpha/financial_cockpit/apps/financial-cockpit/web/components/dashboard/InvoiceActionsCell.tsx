'use client';

import { useCallback, useEffect, useState } from 'react';

import { InvoicePdfPreviewModal } from '@/components/dashboard/InvoicePdfPreviewModal';
import { PENNYLANE_LINK_TITLE, resolvePennylaneTransactionsUrl } from '@/lib/pennylaneUrls';

type InvoiceActionsCellProps = {
  entitySlug: string;
  invoiceId: string;
  organizationSlug: string;
  invoiceType?: 'customer' | 'supplier';
  invoiceRef?: string | null;
  pennylaneTransactionsUrl?: string | null;
  pennylaneCompanyId?: number | null;
};

function buildPdfApiUrl(
  entitySlug: string,
  invoiceId: string,
  options: {
    organizationSlug: string;
    invoiceType?: 'customer' | 'supplier';
    invoiceRef?: string | null;
    disposition?: 'inline' | 'attachment';
  },
): string {
  const params = new URLSearchParams({
    organizationSlug: options.organizationSlug,
  });
  if (options.invoiceType === 'supplier') {
    params.set('type', 'supplier');
  }
  if (options.invoiceRef) {
    params.set('invoiceRef', options.invoiceRef);
  }
  if (options.disposition === 'attachment') {
    params.set('disposition', 'attachment');
  }
  return `/api/entities/${encodeURIComponent(entitySlug)}/invoices/${encodeURIComponent(invoiceId)}/pdf?${params.toString()}`;
}

export function InvoiceActionsCell({
  entitySlug,
  invoiceId,
  organizationSlug,
  invoiceType = 'customer',
  invoiceRef,
  pennylaneTransactionsUrl,
  pennylaneCompanyId,
}: InvoiceActionsCellProps) {
  const [busy, setBusy] = useState<'download' | 'view' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const previewTitle = invoiceRef || invoiceId;
  const pennylaneUrl = resolvePennylaneTransactionsUrl({
    pennylane_transactions_url: pennylaneTransactionsUrl,
    pennylane_company_id: pennylaneCompanyId,
    invoice_ref: invoiceRef,
  });

  const closePreview = useCallback(() => {
    setPreviewOpen(false);
    setPreviewError(null);
    setPreviewUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current);
      }
      return null;
    });
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const runDownload = useCallback(async () => {
    setBusy('download');
    setError(null);

    const apiUrl = buildPdfApiUrl(entitySlug, invoiceId, {
      organizationSlug,
      invoiceType,
      invoiceRef,
      disposition: 'attachment',
    });

    try {
      const response = await fetch(apiUrl);
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { error?: string } | null;
        throw new Error(payload?.error ?? `HTTP ${response.status}`);
      }

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = `${previewTitle.replace(/[^\w.-]+/g, '_')}.pdf`;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Échec du téléchargement');
    } finally {
      setBusy(null);
    }
  }, [entitySlug, invoiceId, invoiceRef, invoiceType, organizationSlug, previewTitle]);

  const runPreview = useCallback(async () => {
    setBusy('view');
    setError(null);
    setPreviewError(null);
    setPreviewOpen(true);
    setPreviewUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current);
      }
      return null;
    });

    const apiUrl = buildPdfApiUrl(entitySlug, invoiceId, {
      organizationSlug,
      invoiceType,
      invoiceRef,
      disposition: 'inline',
    });

    try {
      const response = await fetch(apiUrl);
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { error?: string } | null;
        throw new Error(payload?.error ?? `HTTP ${response.status}`);
      }

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      setPreviewUrl(objectUrl);
    } catch (actionError) {
      setPreviewError(
        actionError instanceof Error ? actionError.message : 'Échec du chargement du PDF',
      );
    } finally {
      setBusy(null);
    }
  }, [entitySlug, invoiceId, invoiceRef, invoiceType, organizationSlug]);

  const handlePreviewOpenChange = useCallback(
    (open: boolean) => {
      if (open) {
        setPreviewOpen(true);
        return;
      }
      closePreview();
    },
    [closePreview],
  );

  return (
    <>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => void runDownload()}
          disabled={busy !== null}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--secondary)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--secondary)] disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Télécharger la facture PDF"
          title="Télécharger la facture PDF"
        >
          <DownloadIcon />
        </button>
        <button
          type="button"
          onClick={() => void runPreview()}
          disabled={busy !== null}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[var(--secondary)] transition-colors hover:bg-[var(--accent)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--secondary)] disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Voir la facture PDF"
          title="Voir la facture PDF"
        >
          <ViewIcon />
        </button>
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
        ) : null}
        {error ? (
          <span className="sr-only" aria-live="polite">
            {error}
          </span>
        ) : null}
      </div>

      <InvoicePdfPreviewModal
        isOpen={previewOpen}
        onOpenChange={handlePreviewOpenChange}
        title={previewTitle}
        pdfUrl={previewUrl}
        loading={busy === 'view' && !previewUrl && !previewError}
        error={previewError}
      />
    </>
  );
}

function DownloadIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M10 3.5v9M6.75 9.25 10 12.5l3.25-3.25M4.5 14.5v1.75A1.75 1.75 0 0 0 6.25 18h7.5a1.75 1.75 0 0 0 1.75-1.75V14.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ViewIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M2.5 10s2.75-5 7.5-5 7.5 5 7.5 5-2.75 5-7.5 5-7.5-5-7.5-5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <circle cx="10" cy="10" r="2.25" stroke="currentColor" strokeWidth="1.5" />
    </svg>
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
