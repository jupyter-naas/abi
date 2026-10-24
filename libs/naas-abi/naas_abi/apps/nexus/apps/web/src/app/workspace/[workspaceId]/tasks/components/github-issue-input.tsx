'use client';

import { ExternalLink } from 'lucide-react';
import { githubIssueRef } from '@/lib/tasks';

/** True for an empty value (no issue) or a GitHub issue URL the API accepts. */
export const isGithubIssueUrl = (value: string) => !value.trim() || githubIssueRef(value) !== null;

/** A GitHub issue URL field: says when the link is not an issue, opens it when it is. */
export function GithubIssueInput({
  id,
  value,
  onChange,
  onCommit,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  /** Leaving the field (or Enter): save there, once the value is valid. */
  onCommit?: () => void;
}) {
  const valid = isGithubIssueUrl(value);
  const ref = githubIssueRef(value);
  return (
    <div className="tasks-github-field">
      <div className="tasks-github-field-row">
        <input
          id={id}
          type="url"
          inputMode="url"
          className="tasks-drawer-input"
          value={value}
          maxLength={500}
          placeholder="https://github.com/owner/repo/issues/42"
          aria-invalid={!valid}
          aria-describedby={valid ? undefined : `${id}-error`}
          onChange={(e) => onChange(e.target.value)}
          onBlur={() => valid && onCommit?.()}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              (e.currentTarget as HTMLInputElement).blur();
            }
          }}
        />
        {ref && (
          <a
            href={value.trim()}
            target="_blank"
            rel="noreferrer"
            className="tasks-icon-button tasks-github-open"
            title={`Open ${ref} on GitHub`}
            aria-label={`Open ${ref} on GitHub`}
          >
            <ExternalLink size={13} />
          </a>
        )}
      </div>
      {!valid && (
        <p id={`${id}-error`} className="tasks-github-error">
          Paste an issue link: https://github.com/owner/repo/issues/42
        </p>
      )}
    </div>
  );
}
