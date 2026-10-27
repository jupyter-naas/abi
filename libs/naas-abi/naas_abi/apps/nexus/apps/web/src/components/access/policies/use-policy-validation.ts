'use client';

import { useEffect, useState } from 'react';
import type { IamAdminApi } from '@/lib/iam-admin/api';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { PolicySource, PolicyValidation } from '@/lib/iam-admin/types';

export type ValidationState = {
  /** IAM's verdict on the latest source; null before the first answer. */
  result: PolicyValidation | null;
  /** The source was edited and IAM has not answered yet. */
  pending: boolean;
  /** The validation call itself failed (not a verdict). */
  failure: string | null;
};

export const VALIDATION_DELAY_MS = 350;

/**
 * Asks IAM what it thinks of the document as it is edited (debounced), so its errors show
 * under the editor before anything is saved. A stale answer never replaces a newer one.
 * With ``scope`` (an org or a workspace) it is checked as a policy that level owns.
 */
export function usePolicyValidation(
  api: IamAdminApi,
  source: PolicySource | null,
  delayMs: number = VALIDATION_DELAY_MS,
  scope?: string,
): ValidationState {
  const [state, setState] = useState<ValidationState>({ result: null, pending: false, failure: null });
  const key = source ? JSON.stringify(source) : null;

  useEffect(() => {
    if (key === null) {
      setState({ result: null, pending: false, failure: null });
      return;
    }
    let cancelled = false;
    setState((previous) => ({ ...previous, pending: true }));
    const timer = setTimeout(() => {
      api
        .validatePolicy(JSON.parse(key) as PolicySource, scope)
        .then((result) => !cancelled && setState({ result, pending: false, failure: null }))
        .catch((error: unknown) => {
          if (cancelled) return;
          setState({
            result: null,
            pending: false,
            failure: error instanceof IamAdminError ? error.message : String(error),
          });
        });
    }, delayMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [api, key, delayMs, scope]);

  return state;
}
