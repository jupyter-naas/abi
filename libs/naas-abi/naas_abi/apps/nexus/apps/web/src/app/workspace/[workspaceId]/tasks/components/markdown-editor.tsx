'use client';

import { useLayoutEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Notion-style Markdown field: the text reads rendered, and a click turns it
 * back into Markdown source to edit. It leaves edit mode on blur.
 */
export function MarkdownEditor({
  value,
  onChange,
  onBlur,
  placeholder = 'Write something, or use Markdown…',
  maxLength,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  placeholder?: string;
  maxLength?: number;
  ariaLabel?: string;
}) {
  const [editing, setEditing] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);

  // Grow with the text instead of scrolling inside a small box.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [value, editing]);

  if (editing) {
    return (
      <div className="tasks-markdown-editing">
        <textarea
          ref={ref}
          autoFocus
          className="tasks-markdown-source"
          value={value}
          maxLength={maxLength}
          aria-label={ariaLabel}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          onBlur={() => {
            setEditing(false);
            onBlur?.();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              // Leave the field, not the dialog around it.
              e.stopPropagation();
              e.nativeEvent.stopImmediatePropagation();
              e.currentTarget.blur();
            }
          }}
        />
        <p className="tasks-markdown-hint">
          Markdown: # Heading · **bold** · *italic* · - list · - [ ] to-do · `code` · [link](url)
        </p>
      </div>
    );
  }

  return (
    <div
      role="textbox"
      tabIndex={0}
      aria-label={ariaLabel}
      className="tasks-markdown"
      onClick={(e) => {
        // Links stay clickable in the rendered text.
        if (!(e.target as HTMLElement).closest('a')) setEditing(true);
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && e.target === e.currentTarget) {
          e.preventDefault();
          setEditing(true);
        }
      }}
    >
      {value.trim() ? (
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ href, children }) => (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            ),
          }}
        >
          {value}
        </ReactMarkdown>
      ) : (
        <span className="tasks-markdown-placeholder">{placeholder}</span>
      )}
    </div>
  );
}
