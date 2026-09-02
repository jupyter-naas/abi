'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

type WorkspaceMarkProps = {
  name?: string;
  icon?: string;
  logoUrl?: string;
  logoEmoji?: string;
  fallbackLetter?: string;
  letterClassName: string;
};

export function WorkspaceMark({
  name,
  icon,
  logoUrl,
  logoEmoji,
  fallbackLetter = 'N',
  letterClassName,
}: WorkspaceMarkProps) {
  const [imgReady, setImgReady] = useState(false);

  useEffect(() => {
    setImgReady(false);
  }, [logoUrl]);

  const letter = logoEmoji || icon || name?.charAt(0) || fallbackLetter;

  return (
    <>
      {(!logoUrl || !imgReady) && <span className={letterClassName}>{letter}</span>}
      {logoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logoUrl}
          alt={name || ''}
          className={imgReady ? 'absolute inset-0 h-full w-full object-cover' : 'hidden'}
          onLoad={() => setImgReady(true)}
          onError={() => setImgReady(false)}
        />
      ) : null}
    </>
  );
}

type WorkspaceMarkFrameProps = {
  children: React.ReactNode;
  className?: string;
  backgroundColor?: string;
};

/** Square chrome around a workspace mark. No accent ring. */
export function WorkspaceMarkFrame({
  children,
  className,
  backgroundColor,
}: WorkspaceMarkFrameProps) {
  return (
    <span
      className={cn(
        'relative flex flex-shrink-0 items-center justify-center overflow-hidden p-0',
        className,
      )}
      style={backgroundColor ? { backgroundColor } : undefined}
    >
      {children}
    </span>
  );
}
