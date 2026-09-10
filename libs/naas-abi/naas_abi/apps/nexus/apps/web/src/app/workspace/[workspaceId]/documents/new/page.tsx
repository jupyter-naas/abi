'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { DocumentsMenuBar } from '@/components/documents/documents-menu-bar';
import { DocumentsStatusBar } from '@/components/documents/documents-status-bar';
import { documentsApiErrorMessage, startNewDocument } from '@/lib/create-documents-project';

export default function NewDocumentsProjectPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const base = `/workspace/${workspaceId}/documents`;
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (!workspaceId || started.current) return;
    started.current = true;
    void startNewDocument(workspaceId, (href) => router.replace(href)).catch((e) => {
      setError(documentsApiErrorMessage((e as Error).message, 'Could not create the document.'));
    });
  }, [workspaceId, router]);

  return (
    <div className="flex h-full flex-col">
      <Header
        title="New Presentation"
        nav={<DocumentsMenuBar onNewPresentation={() => router.push(`${base}/new`)} />}
      />
      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}
      <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
        {!error && <Loader2 size={16} className="animate-spin" />}
        {error || 'Opening Minimal Light…'}
      </div>
      <DocumentsStatusBar />
    </div>
  );
}
