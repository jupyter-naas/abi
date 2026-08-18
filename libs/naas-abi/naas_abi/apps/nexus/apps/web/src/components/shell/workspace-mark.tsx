'use client';

import { useEffect, useState } from 'react';

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
          className={imgReady ? 'h-full w-full object-cover' : 'hidden'}
          onLoad={() => setImgReady(true)}
          onError={() => setImgReady(false)}
        />
      ) : null}
    </>
  );
}
