import type { BannerType, PageBannerConfig } from '@/lib/types';

type BannerStyle = {
  /** Tint background + border, translucent so it holds up in light and dark. */
  background: string;
  border: string;
  /** Accent used for the icon. */
  accent: string;
  Icon: React.ComponentType<{ className?: string }>;
};

function WarningIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m0 3.75h.008M10.363 3.591 2.257 17.727A1.5 1.5 0 0 0 3.557 20h16.886a1.5 1.5 0 0 0 1.3-2.273L13.637 3.591a1.5 1.5 0 0 0-2.274 0Z"
      />
    </svg>
  );
}

function InfoIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M11.25 11.25h.75v4.5h.75M12 8.25h.008M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
      />
    </svg>
  );
}

const BANNER_STYLES: Record<BannerType, BannerStyle> = {
  warning: {
    background: 'rgba(245, 158, 11, 0.12)',
    border: 'rgba(245, 158, 11, 0.40)',
    accent: '#b45309',
    Icon: WarningIcon,
  },
  info: {
    background: 'rgba(59, 130, 246, 0.12)',
    border: 'rgba(59, 130, 246, 0.40)',
    accent: '#1d4ed8',
    Icon: InfoIcon,
  },
};

type PageBannerProps = {
  banner: PageBannerConfig;
  className?: string;
};

/**
 * Reusable notice banner configured per page in config.yaml. `warning` renders
 * amber, `info` renders blue; both use translucent tints so they read in light
 * and dark themes, with the body text inheriting the current `--text` color.
 */
export function PageBanner({ banner, className = '' }: PageBannerProps) {
  const style = BANNER_STYLES[banner.type] ?? BANNER_STYLES.info;
  const { Icon } = style;

  return (
    <div
      role="status"
      className={`flex items-start gap-3 border px-4 py-3 text-sm text-[var(--text)] ${className}`}
      style={{ backgroundColor: style.background, borderColor: style.border }}
    >
      <span className="mt-0.5 shrink-0" style={{ color: style.accent }}>
        <Icon className="h-5 w-5" />
      </span>
      <span className="min-w-0 flex-1 leading-snug">{banner.text}</span>
    </div>
  );
}
