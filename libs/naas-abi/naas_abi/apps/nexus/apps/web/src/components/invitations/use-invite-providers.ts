'use client';

import { useEffect, useState } from 'react';
import {
  NO_PROVIDERS,
  defaultInviteProvider,
  fetchInviteProviders,
  providerToSend,
  type InviteProvider,
  type InviteProviders,
} from '@/lib/invitations';

/**
 * The identity providers an invitation can go through, read each time the
 * dialog opens (`active`), and the one picked.
 */
export function useInviteProviders(active: boolean) {
  const [known, setKnown] = useState<InviteProviders>(NO_PROVIDERS);
  const [picked, setPicked] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    void fetchInviteProviders().then((found) => {
      if (cancelled) return;
      setKnown(found);
      setPicked(defaultInviteProvider(found));
    });
    return () => {
      cancelled = true;
    };
  }, [active]);

  const chosen: InviteProvider | undefined = known.providers.find(
    (p) => p.name === (picked ?? defaultInviteProvider(known))
  );
  return {
    known,
    picked: chosen?.name,
    setPicked,
    chosen,
    // What the invite request names: only when there is a choice to make.
    providerToSend: () => providerToSend(known, picked),
    // More than one provider: the dialog offers the choice.
    choosable: known.enabled && known.providers.length > 1,
  };
}
