'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { synchronizePermissionContext, usePermissionCache, usePermissionRevision, usePermissionSessionKey } from '@/lib/permission-cache';
import { createIamAdminApi, isSessionIamApi, type IamAdminApi } from './api';
import type { AccessView } from './types';

export type IamAccess = {
  /** `null` while loading or when it could not be read. */
  access: AccessView | null;
  loading: boolean;
  error: string | null;
  /** Whether the caller may perform an `iam:*` action (false until known). */
  can: (action: string) => boolean;
};

export type IamAccessOptions = {
  /** Ask nothing (yet): the scope is not known. `loading` is false and `access` null. */
  skip?: boolean;
  /** Ask again when it changes (a page's Refresh). */
  reload?: number;
};

const clients = new WeakMap<IamAdminApi, number>();
let nextClient = 0;
function accessKey(api: IamAdminApi, scope?: string): string {
  if (!clients.has(api)) clients.set(api, ++nextClient);
  return `client:iam:${clients.get(api)}:${JSON.stringify(scope ?? 'abi:')}`;
}

/** Also isolates injected API implementations; default clients share the authFetch wire cache. */
export async function readIamAccess(api: IamAdminApi, scope?: string, refresh = false): Promise<AccessView> {
  const load = () => refresh ? api.access(scope, { refresh: true }) : api.access(scope);
  synchronizePermissionContext();
  if (typeof window === 'undefined' || !usePermissionCache.getState().enabled || isSessionIamApi(api)) return load();
  const response = await usePermissionCache.getState().read(
    accessKey(api, scope), async () => new Response(JSON.stringify(await load()), {
      headers: { 'Content-Type': 'application/json' },
    }), { force: refresh },
  );
  return response.json() as Promise<AccessView>;
}

/**
 * What the caller may do (`GET /api/iam/admin/access`). Without a scope the attachment actions
 * are decided on the platform; with a container (`abi:nexus:organization/<org>`, a workspace's)
 * at that scope, so an org admin sees attach and detach on their org.
 */
export function useIamAccess(scope?: string, api?: IamAdminApi, { skip = false, reload = 0 }: IamAccessOptions = {}): IamAccess {
  const client = useMemo(() => api ?? createIamAdminApi(), [api]);
  const session = usePermissionSessionKey();
  const revision = usePermissionRevision();
  const previousReload = useRef(reload);
  // What is asked: the scope (and the reload), none while skipped. An answer counts only
  // for the question it answered, so a new scope is loading from its first render on,
  // never the previous scope's access, nor "no access" before the read starts.
  const asked = skip ? null : JSON.stringify([session, accessKey(client, scope), reload]);
  const [answer, setAnswer] = useState<{ asked: string; access: AccessView | null; error: string | null } | null>(null);

  useEffect(() => {
    if (asked === null) return;
    let cancelled = false;
    const refresh = previousReload.current !== reload;
    previousReload.current = reload;
    readIamAccess(client, scope, refresh)
      .then((view) => !cancelled && setAnswer({ asked, access: view, error: null }))
      .catch((e: unknown) => {
        if (!cancelled) setAnswer({ asked, access: null, error: e instanceof Error ? e.message : String(e) });
      });
    return () => {
      cancelled = true;
    };
    // The scope and the reload are read through ``asked``.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, asked, revision]);

  const settled = asked !== null && answer?.asked === asked;
  const access = settled ? answer.access : null;
  const error = settled ? answer.error : null;
  const loading = asked !== null && !settled;
  const can = useCallback((action: string) => access?.actions[action] === true, [access]);
  return { access, loading, error, can };
}
