'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useIsMobile } from '@/hooks/use-is-mobile';

export default function AccountPage() {
  const isMobile = useIsMobile();
  const router = useRouter();

  // Desktop keeps the old default: land on Profile. Mobile stays on /account
  // so the layout can show the settings list first (chat-style list-then-detail).
  useEffect(() => {
    if (!isMobile) {
      router.replace('/account/profile');
    }
  }, [isMobile, router]);

  return null;
}
