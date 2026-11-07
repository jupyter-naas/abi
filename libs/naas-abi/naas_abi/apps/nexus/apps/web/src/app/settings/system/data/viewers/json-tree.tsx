'use client';

/** A collapsible, typed JSON tree. Understands the document service's tagged values. */
import { createContext, useContext, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown } from 'lucide-react';
import { CopyButton } from '../data-ui';

const ARRAY_PAGE = 100;
const STRING_CLIP = 400;

interface TreeSettings {
  depth: number;
}

const Settings = createContext<TreeSettings>({ depth: 2 });

/** ``{"$t": "datetime", "$v": ...}``: how the document service tags non-JSON values. */
function tagged(value: unknown): { tag: string; value: unknown } | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const keys = Object.keys(value);
  if (keys.length !== 2 || !keys.includes('$t') || !keys.includes('$v')) return null;
  const v = value as { $t: unknown; $v: unknown };
  return typeof v.$t === 'string' ? { tag: v.$t, value: v.$v } : null;
}

function Scalar({ value }: { value: unknown }) {
  const [open, setOpen] = useState(false);
  if (value === null) return <span className="json-null">null</span>;
  if (typeof value === 'boolean') return <span className="json-boolean">{String(value)}</span>;
  if (typeof value === 'number') return <span className="json-number">{String(value)}</span>;
  if (typeof value === 'string') {
    const clipped = !open && value.length > STRING_CLIP;
    return (
      <span className="json-string">
        &quot;{clipped ? value.slice(0, STRING_CLIP) : value}
        {clipped && (
          <button type="button" className="json-more" onClick={() => setOpen(true)}>
            … {value.length - STRING_CLIP} more
          </button>
        )}
        &quot;
      </span>
    );
  }
  return <span className="json-string">{String(value)}</span>;
}

function Summary({ value }: { value: object }) {
  if (Array.isArray(value)) return <span className="json-summary">[{value.length} items]</span>;
  const count = Object.keys(value).length;
  return <span className="json-summary">{`{${count} ${count === 1 ? 'key' : 'keys'}}`}</span>;
}

function Node({ name, value, depth }: { name: ReactNode; value: unknown; depth: number }) {
  const settings = useContext(Settings);
  const [open, setOpen] = useState(depth < settings.depth);
  const [shown, setShown] = useState(ARRAY_PAGE);
  const tag = tagged(value);

  if (tag) {
    return (
      <div className="json-row">
        <span className="json-indent" style={{ width: depth * 14 }} />
        <span className="json-caret-space" />
        {name}
        <span className="json-tag">{tag.tag}</span>
        <Scalar value={tag.value} />
      </div>
    );
  }

  if (value === null || typeof value !== 'object') {
    return (
      <div className="json-row json-row-leaf">
        <span className="json-indent" style={{ width: depth * 14 }} />
        <span className="json-caret-space" />
        {name}
        <Scalar value={value} />
        <span className="json-row-copy">
          <CopyButton value={typeof value === 'string' ? value : JSON.stringify(value)} label="Copy value" />
        </span>
      </div>
    );
  }

  const entries: [string, unknown][] = Array.isArray(value)
    ? value.slice(0, shown).map((v, i) => [String(i), v])
    : Object.entries(value);
  const hidden = Array.isArray(value) ? value.length - shown : 0;

  return (
    <>
      <div className="json-row">
        <span className="json-indent" style={{ width: depth * 14 }} />
        <button
          type="button"
          className="json-caret"
          aria-expanded={open}
          aria-label={open ? 'Collapse' : 'Expand'}
          onClick={() => setOpen(!open)}
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </button>
        {name}
        {open ? (
          <span className="json-brace">{Array.isArray(value) ? '[' : '{'}</span>
        ) : (
          <button type="button" className="json-collapsed" onClick={() => setOpen(true)}>
            <Summary value={value} />
          </button>
        )}
        <span className="json-row-copy">
          <CopyButton value={JSON.stringify(value, null, 2)} label="Copy as JSON" />
        </span>
      </div>
      {open && (
        <>
          {entries.map(([key, child]) => (
            <Node
              key={key}
              depth={depth + 1}
              value={child}
              name={
                Array.isArray(value) ? (
                  <span className="json-index">{key}</span>
                ) : (
                  <span className="json-key">{key}</span>
                )
              }
            />
          ))}
          {hidden > 0 && (
            <div className="json-row">
              <span className="json-indent" style={{ width: (depth + 1) * 14 }} />
              <button type="button" className="json-more" onClick={() => setShown(shown + ARRAY_PAGE)}>
                Show {Math.min(hidden, ARRAY_PAGE)} more of {hidden}
              </button>
            </div>
          )}
          <div className="json-row">
            <span className="json-indent" style={{ width: depth * 14 }} />
            <span className="json-caret-space" />
            <span className="json-brace">{Array.isArray(value) ? ']' : '}'}</span>
          </div>
        </>
      )}
    </>
  );
}

/** ``value`` as a tree, expanded ``depth`` levels; expand or collapse everything at once. */
export function JsonTree({ value, depth = 2, toolbar = true }: { value: unknown; depth?: number; toolbar?: boolean }) {
  const [mode, setMode] = useState<{ depth: number; version: number }>({ depth, version: 0 });
  return (
    <div className="json-tree">
      {toolbar && value !== null && typeof value === 'object' && (
        <div className="json-toolbar">
          <button
            type="button"
            className="data-text-button"
            onClick={() => setMode({ depth: Infinity, version: mode.version + 1 })}
          >
            <ChevronsUpDown size={13} aria-hidden="true" /> Expand all
          </button>
          <button
            type="button"
            className="data-text-button"
            onClick={() => setMode({ depth: 1, version: mode.version + 1 })}
          >
            <ChevronsDownUp size={13} aria-hidden="true" /> Collapse
          </button>
          <span className="data-spacer" />
          <CopyButton value={JSON.stringify(value, null, 2)} label="Copy JSON" />
        </div>
      )}
      <Settings.Provider value={{ depth: mode.depth }}>
        <div className="json-body" key={mode.version}>
          <Node name={null} value={value} depth={0} />
        </div>
      </Settings.Provider>
    </div>
  );
}
