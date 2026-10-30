'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { createIamAdminApi, type IamAdminApi } from './api';
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

/**
 * What the caller may do (`GET /api/iam/admin/access`). Without a scope the attachment actions
 * are decided on the platform; with a container (`abi:nexus:organization/<org>`, a workspace's)
 * at that scope, so an org admin sees attach and detach on their org.
 */
export function useIamAccess(scope?: string, api?: IamAdminApi, { skip = false, reload = 0 }: IamAccessOptions = {}): IamAccess {
  const client = useMemo(() => api ?? createIamAdminApi(), [api]);
  const [access, setAccess] = useState<AccessView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!skip);

  useEffect(() => {
    if (skip) {
      setAccess(null);
      setError(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    client
      .access(scope)
      .then((view) => {
        if (cancelled) return;
        setAccess(view);
        setError(null);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setAccess(null);
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [client, scope, skip, reload]);

  const can = useCallback((action: string) => access?.actions[action] === true, [access]);
  return { access, loading, error, can };
}
