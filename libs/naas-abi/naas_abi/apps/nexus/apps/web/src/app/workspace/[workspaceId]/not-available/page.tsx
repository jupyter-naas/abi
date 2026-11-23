'use client';

import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { useTenant } from '@/contexts/tenant-context';

function isLightColor(hex: string): boolean {
  const c = hex.replace('#', '');
  const r = parseInt(c.substring(0, 2), 16);
  const g = parseInt(c.substring(2, 4), 16);
  const b = parseInt(c.substring(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6;
}

export default function WorkspaceFeatureNotAvailablePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const tenant = useTenant();
  const workspaceId = String(params.workspaceId ?? '');
  const from = searchParams.get('from');
  const fallbackPath = `/workspace/${workspaceId}/chat`;
  const blockedPath = from ? decodeURIComponent(from) : null;

  const primaryColor = tenant.primary_color || '#34D399';
  const accentColor = tenant.accent_color || '#1FA574';
  const cardColor = tenant.login_card_color || '#FFFFFF';
  const radius = `${tenant.login_border_radius || '0'}px`;
  const cardIsLight = isLightColor(cardColor);
  const textColor = tenant.login_text_color || (cardIsLight ? '#1a1a1a' : '#ffffff');
  const mutedTextColor = cardIsLight ? 'rgba(0,0,0,0.55)' : 'rgba(255,255,255,0.55)';

  return (
    <div className="flex h-full w-full items-center justify-center bg-background p-6">
      <div
        className="w-full"
        style={{
          maxWidth: tenant.login_card_max_width || '440px',
          padding: tenant.login_card_padding || '2.5rem 3rem 3rem',
          backgroundColor: cardColor,
          borderRadius: radius,
          color: textColor,
        }}
      >
        <h1 className="text-2xl font-bold leading-tight">Feature not available</h1>
        <p className="mt-3 text-sm" style={{ color: mutedTextColor }}>
          Your workspace role does not grant access to this section yet.
        </p>
        {blockedPath ? (
          <p className="mt-2 text-xs" style={{ color: mutedTextColor }}>
            Blocked path: {blockedPath}
          </p>
        ) : null}
        <Link
          href={fallbackPath}
          className="mt-6 flex h-11 w-full items-center justify-center px-4 text-sm font-medium text-white transition-all"
          style={{ backgroundColor: primaryColor, borderRadius: radius }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = accentColor;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = primaryColor;
          }}
        >
          Go to an available section
        </Link>
      </div>
    </div>
  );
}
