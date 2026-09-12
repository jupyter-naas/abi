'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { DocumentsMenuBar } from '@/components/documents/documents-menu-bar';
import { DocumentsStatusBar } from '@/components/documents/documents-status-bar';
import { OfficeCreateLoader } from '@/components/office/office-create-loader';
import { officeCreateTemplateId } from '@/components/office/office-create';
import { documentsApiErrorMessage, startNewDocument } from '@/lib/create-documents-project';

export default function NewDocumentsProjectPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<'creating' | 'opening'>('creating');
  const started = useRef(false);

  const begin = useCallback(
    (templateId?: string) => {
      if (!workspaceId) return;
      setError(null);
      setPhase('creating');
      void startNewDocument(
        workspaceId,
        (href) => {
          setPhase('opening');
          router.replace(href);
        },
        templateId,
      ).catch((e) => {
        setError(documentsApiErrorMessage((e as Error).message, 'Could not create the document.'));
      });
    },
    [workspaceId, router],
  );

  useEffect(() => {
    if (!workspaceId || started.current) return;
    started.current = true;
    begin(officeCreateTemplateId(searchParams));
  }, [workspaceId, begin, searchParams]);

  return (
    <div className="flex h-full flex-col">
      <Header
        title="New document"
        nav={
          <DocumentsMenuBar
            onNewPresentation={() => {
              if (!error) return;
              begin();
            }}
            newDisabled={!error}
          />
        }
      />
      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}
      <OfficeCreateLoader kind="document" phase={phase} error={error} />
      <DocumentsStatusBar />
    </div>
  );
}
