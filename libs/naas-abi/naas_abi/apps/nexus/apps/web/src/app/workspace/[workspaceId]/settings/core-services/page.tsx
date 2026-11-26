'use client';

/**
 * Settings › Access › Services: how far people go with each core service in the workspace, for a
 * policy picked in the header ("<W> access" by default, `?policy=`). `CoreServices`.
 */
import { Suspense } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';
import { SettingsLoading } from '@/components/settings/settings-ui';
import { CoreServices } from './core-services';
// The level choices (General's CSS).
import '../general/general.css';

function Services() {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const pathname = usePathname();
  const policy = useSearchParams().get('policy');
  return (
    <CoreServices
      key={workspaceId}
      workspaceId={workspaceId}
      initialPolicy={policy}
      onPolicyChange={(next) => router.replace(next ? `${pathname}?policy=${encodeURIComponent(next)}` : pathname)}
    />
  );
}

export default function CoreServicesSettingsPage() {
  return (
    <Suspense fallback={<SettingsLoading label="Loading services…" />}>
      <Services />
    </Suspense>
  );
}
