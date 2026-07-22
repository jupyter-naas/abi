'use client';

import { useEffect } from 'react';
import {
  Dialog,
  Heading,
  Modal,
  ModalOverlay,
} from 'react-aria-components';

type InvoicePdfPreviewModalProps = {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  pdfUrl: string | null;
  loading?: boolean;
  error?: string | null;
};

export function InvoicePdfPreviewModal({
  isOpen,
  onOpenChange,
  title,
  pdfUrl,
  loading = false,
  error = null,
}: InvoicePdfPreviewModalProps) {
  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen]);

  return (
    <ModalOverlay
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      isDismissable
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 backdrop-blur-[1px]"
    >
      <Modal className="flex w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl outline-none max-h-[92vh]">
        <Dialog className="flex min-h-0 flex-1 flex-col outline-none">
          {({ close }) => (
            <>
              <header className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
                <Heading
                  slot="title"
                  className="truncate text-sm font-semibold text-[var(--text)]"
                >
                  {title}
                </Heading>
                <button
                  type="button"
                  onClick={close}
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[var(--text-muted)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--secondary)]"
                  aria-label="Fermer l’aperçu"
                >
                  <span aria-hidden className="text-lg leading-none">
                    ×
                  </span>
                </button>
              </header>

              <div className="relative min-h-0 flex-1 bg-[var(--surface-2)]">
                {loading ? (
                  <div className="flex h-[min(70vh,720px)] items-center justify-center text-sm text-[var(--text-muted)]">
                    Chargement du PDF…
                  </div>
                ) : null}

                {!loading && error ? (
                  <div className="flex h-[min(70vh,720px)] items-center justify-center px-6 text-center text-sm text-[var(--text-muted)]">
                    {error}
                  </div>
                ) : null}

                {!loading && !error && pdfUrl ? (
                  <iframe
                    src={pdfUrl}
                    title={title}
                    className="h-[min(70vh,720px)] w-full border-0"
                  />
                ) : null}
              </div>
            </>
          )}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
