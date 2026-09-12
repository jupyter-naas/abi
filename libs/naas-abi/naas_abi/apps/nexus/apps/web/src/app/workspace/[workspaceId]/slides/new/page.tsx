'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { SlidesMenuBar } from '@/components/slides/slides-menu-bar';
import { SlidesStatusBar } from '@/components/slides/slides-status-bar';
import { OfficeCreateLoader } from '@/components/office/office-create-loader';
import { officeCreateTemplateId } from '@/components/office/office-create';
import { slidesApiErrorMessage, startNewPresentation } from '@/lib/create-slides-project';

export default function NewSlidesProjectPage() {
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
      void startNewPresentation(
        workspaceId,
        (href) => {
          setPhase('opening');
          router.replace(href);
        },
        templateId,
      ).catch((e) => {
        setError(slidesApiErrorMessage((e as Error).message, 'Could not create the deck.'));
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
        title="New Presentation"
        nav={
          <SlidesMenuBar
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
      <OfficeCreateLoader kind="deck" phase={phase} error={error} />
      <SlidesStatusBar />
    </div>
  );
}
