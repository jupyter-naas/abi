'use client';

import { AppWindow, Bot, GitBranch, KeyRound, ToggleRight, Workflow, type LucideIcon } from 'lucide-react';
import type { BuilderGroup, BuilderItem, BuilderSectionId } from './builder-model';
import './policy-builder.css';

const SECTION_ICONS: Record<BuilderSectionId, LucideIcon> = {
  agents: Bot,
  apps: AppWindow,
  workflows: Workflow,
  pipelines: GitBranch,
  actions: KeyRound,
  features: ToggleRight,
};

/** A module's own icon when it gives a picture, else its type's. */
function ItemIcon({ item, section }: { item: BuilderItem; section: BuilderSectionId }) {
  if (item.icon && /^(https?:|\/|data:image\/)/.test(item.icon)) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={item.icon} alt="" className="access-builder-icon" />;
  }
  const Icon = SECTION_ICONS[section];
  return <Icon size={14} className="access-builder-icon" aria-hidden />;
}

/**
 * What the caller may grant at the scope, as checkboxes: per module its agents, apps,
 * workflows, pipelines and declared actions, then the Nexus features. ``refused`` holds IAM's
 * refusal of an item, shown beside it. ``kept`` counts the statements the builder cannot show
 * (they stay in the policy: the Statements view edits them).
 */
export function PolicyBuilder({
  groups,
  selected,
  onToggle,
  kept,
  refused = {},
  readOnly = false,
}: {
  groups: BuilderGroup[];
  selected: ReadonlySet<string>;
  onToggle: (keys: string[], on: boolean) => void;
  kept: number;
  refused?: Record<string, string>;
  readOnly?: boolean;
}) {
  if (groups.length === 0) {
    return (
      <p className="access-policy-notice" role="status">
        You hold nothing here that you could grant: write statements in the Statements view instead.
      </p>
    );
  }
  return (
    <div className="access-builder" aria-label="Policy builder">
      {kept > 0 && (
        <p className="access-policy-muted">
          {kept} other statement{kept === 1 ? '' : 's'} stay{kept === 1 ? 's' : ''} as written (Statements view).
        </p>
      )}
      {groups.map((group) => {
        const keys = group.sections.flatMap((s) => s.items.map((i) => i.key));
        const chosen = keys.filter((k) => selected.has(k)).length;
        return (
          <fieldset key={group.id} className="access-builder-group" data-builder-group={group.id}>
            <legend className="access-builder-legend">
              <label className="access-checkbox">
                <input
                  type="checkbox"
                  aria-label={`All of ${group.label}`}
                  checked={chosen === keys.length}
                  ref={(el) => {
                    if (el) el.indeterminate = chosen > 0 && chosen < keys.length;
                  }}
                  disabled={readOnly}
                  onChange={(e) => onToggle(keys, e.target.checked)}
                />
                <span>{group.label}</span>
              </label>
              <span className="access-policy-muted">
                {chosen} of {keys.length}
              </span>
            </legend>
            {group.sections.map((section) => (
              <div key={section.id} className="access-builder-section">
                <h5 className="access-builder-heading">{section.label}</h5>
                <ul className="access-builder-items">
                  {section.items.map((item) => (
                    <li key={item.key} className="access-builder-item" data-builder-item={item.key}>
                      <label className="access-checkbox" title={item.description || undefined}>
                        <input
                          type="checkbox"
                          aria-label={`${group.label}: ${item.label}`}
                          checked={selected.has(item.key)}
                          disabled={readOnly}
                          onChange={(e) => onToggle([item.key], e.target.checked)}
                        />
                        <ItemIcon item={item} section={section.id} />
                        <span>{item.label}</span>
                      </label>
                      {refused[item.key] && (
                        <p className="access-builder-refused" role="alert">
                          {refused[item.key]}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </fieldset>
        );
      })}
    </div>
  );
}
