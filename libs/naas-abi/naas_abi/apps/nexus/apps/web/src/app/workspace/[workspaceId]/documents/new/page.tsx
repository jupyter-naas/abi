'use client';

import { useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { OfficeCreateLoader } from '@/components/office/office-create-loader';
import { officeCreateTemplateId } from '@/components/office/office-create';
import {
  beginOfficeCreate,
  failOfficeCreate,
  setOfficeCreatePhase,
  useOfficeCreateStore,
} from '@/components/office/office-create-state';

export default function NewDocumentsProjectPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const started = useRef(false);
  const phase = useOfficeCreateStore((s) => s.phase);
  const error = useOfficeCreateStore((s) => s.error);

  useEffect(() => {
    if (!workspaceId || started.current) return;
    started.current = true;
    if (!useOfficeCreateStore.getState().kind) beginOfficeCreate('document');
    const templateId = officeCreateTemplateId(
      typeof window === 'undefined' ? null : new URLSearchParams(window.location.search),
    );
    void (async () => {
      const fallback = 'Could not create the document.';
      let errorMessage = (detail: unknown) => (detail ? String(detail) : fallback);
      try {
        // A failed chunk load (deploy, network) must surface too, not spin.
        const lib = await import('@/lib/create-documents-project');
        const { documentsApiErrorMessage, startNewDocument } = lib;
        errorMessage = (detail) => documentsApiErrorMessage(detail, fallback);
        await startNewDocument(
          workspaceId,
          (href) => {
            setOfficeCreatePhase('opening');
            router.replace(href);
          },
          templateId,
        );
      } catch (e) {
        failOfficeCreate(errorMessage((e as Error).message));
      }
    })();
  }, [workspaceId, router]);

  return <OfficeCreateLoader kind="document" phase={phase} error={error} />;
}
