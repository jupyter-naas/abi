'use client';

/**
 * Settings › Access › Modules: what a policy of the workspace allows of each module, "<W> access"
 * (its offer) by default (`WorkspaceModules`). The policy edited is kept in the URL (`?policy=`).
 */
import { Suspense } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';
import { SettingsLoading } from '@/components/settings/settings-ui';
import { WorkspaceModules } from './modules';

function Modules() {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const pathname = usePathname();
  const policy = useSearchParams().get('policy');
  return (
    <WorkspaceModules
      key={workspaceId}
      workspaceId={workspaceId}
      initialPolicy={policy}
      onPolicyChange={(next) => router.replace(next ? `${pathname}?policy=${encodeURIComponent(next)}` : pathname)}
    />
  );
}

export default function ModulesSettingsPage() {
  return (
    <Suspense fallback={<SettingsLoading label="Loading modules…" />}>
      <Modules />
    </Suspense>
  );
}
