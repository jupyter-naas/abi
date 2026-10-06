'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { SheetsMenuBar } from '@/components/sheets/sheets-menu-bar';
import { SheetsStatusBar } from '@/components/sheets/sheets-status-bar';
import { sheetsApiErrorMessage, startNewWorkbook } from '@/lib/create-sheets-project';

export default function NewSheetsProjectPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const base = `/workspace/${workspaceId}/sheets`;
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (!workspaceId || started.current) return;
    started.current = true;
    void startNewWorkbook(workspaceId, (href) => router.replace(href)).catch((e) => {
      setError(sheetsApiErrorMessage((e as Error).message, 'Could not create the workbook.'));
    });
  }, [workspaceId, router]);

  return (
    <div className="flex h-full flex-col">
      <Header
        title="New Workbook"
        nav={<SheetsMenuBar onNewWorkbook={() => router.push(`${base}/new`)} />}
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
      <SheetsStatusBar />
    </div>
  );
}
