'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  buildReferentialsIndex,
  type ReferentialsIndex,
  type ReferentialsPayload,
} from '@/lib/pnl/referentials';

type UseReferentialsOptions = {
  entitySlug: string;
  companySlug?: string | null;
};

type UseReferentialsResult = {
  payload: ReferentialsPayload | null;
  index: ReferentialsIndex | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
};

const EMPTY_PAYLOAD: ReferentialsPayload = {
  customers: [],
  suppliers: [],
  categories: [],
};

export function useReferentials({
  entitySlug,
  companySlug,
}: UseReferentialsOptions): UseReferentialsResult {
  const [payload, setPayload] = useState<ReferentialsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (companySlug) {
        params.set('company', companySlug);
      }
      const query = params.toString();
      const response = await fetch(
        `/api/entities/${entitySlug}/referentials${query ? `?${query}` : ''}`,
      );
      if (!response.ok) {
        setError('Impossible de charger les référentiels.');
        setPayload(EMPTY_PAYLOAD);
        return;
      }
      const body = (await response.json()) as ReferentialsPayload;
      setPayload(body);
    } catch {
      setError('Impossible de charger les référentiels.');
      setPayload(EMPTY_PAYLOAD);
    } finally {
      setLoading(false);
    }
  }, [entitySlug, companySlug]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const index = useMemo(
    () => (payload ? buildReferentialsIndex(payload) : null),
    [payload],
  );

  return { payload, index, loading, error, reload };
}
