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
    void import('@/lib/create-documents-project').then(({ documentsApiErrorMessage, startNewDocument }) =>
      startNewDocument(
        workspaceId,
        (href) => {
          setOfficeCreatePhase('opening');
          router.replace(href);
        },
        templateId,
      ).catch((e) => {
        failOfficeCreate(
          documentsApiErrorMessage((e as Error).message, 'Could not create the document.'),
        );
      }),
    );
  }, [workspaceId, router]);

  return <OfficeCreateLoader kind="document" phase={phase} error={error} />;
}
