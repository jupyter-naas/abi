'use client';

import { useCallback, useState } from 'react';

/** A key's value, as it is shown right after it is made. */
export type RevealedSecret = { title: string; value: string };

/**
 * The one place a key's value lives: component state, never storage, the URL or a list.
 * IAM keeps only a hash, so once this is dismissed (or its owner unmounts) the value is gone.
 */
export function useOneTimeSecret() {
  const [secret, setSecret] = useState<RevealedSecret | null>(null);
  const reveal = useCallback((title: string, value: string) => setSecret({ title, value }), []);
  const dismiss = useCallback(() => setSecret(null), []);
  return { secret, reveal, dismiss };
}

export function OneTimeSecretPanel({
  secret,
  onClose,
}: {
  secret: RevealedSecret;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    void navigator.clipboard
      ?.writeText(secret.value)
      .then(() => setCopied(true))
      .catch(() => setCopied(false));
  };
  return (
    <div className="access-sa-secret" role="alert" data-one-time-secret>
      <strong className="access-sa-secret-title">{secret.title}</strong>
      <p className="access-sa-secret-warning">
        Copy this key now. It is shown only once: IAM keeps a hash, so it cannot be shown again.
      </p>
      <code className="access-sa-secret-value system-mono">{secret.value}</code>
      <div className="access-sa-actions">
        <button type="button" className="system-button" onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
        <button type="button" className="system-button system-button-primary" onClick={onClose}>
          I have copied it
        </button>
      </div>
    </div>
  );
}
