'use client';

import './sets-matrix.css';

import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, ChevronRight, Minus } from 'lucide-react';
import type { IamAdminApi } from '@/lib/iam-admin/api';
import type {
  ModuleScopesEntry,
  OrganizationSetView,
  SetParts,
  WorkspaceSetView,
} from '@/lib/iam-admin/types';
import { featureLabel } from '@/app/organizations/[orgId]/settings/lib/feature-labels';
import {
  coverage,
  declaredActions,
  displayCoverage,
  ITEM_TYPES,
  itemsOf,
  moduleMatches,
  outsideOfBound,
  partSummary,
  rowOutside,
  sameParts,
  toggleRow,
  withinBound,
  type Coverage,
  type SetCatalog,
  type SetRow,
} from './sets-model';

export const NOT_IN_ORGANIZATION = 'Not in the organization’s set: recorded here, but not effective.';

type Column = {
  /** `org` for the organization, else the workspace id. */
  key: string;
  kind: 'organization' | 'workspace';
  id: string;
  name: string;
  view: WorkspaceSetView;
  /** What a workspace may hold: its organization's set. None for the organization. */
  bound: SetParts | null;
};

type Part = 'modules' | 'features';

const EVERYTHING: SetParts = { modules: null, features: null };

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

function moduleCounts(entry: ModuleScopesEntry): string {
  const parts = ITEM_TYPES.map(({ type }) => [type, itemsOf(entry, type).length] as const)
    .filter(([, count]) => count > 0)
    .map(([type, count]) => plural(count, type));
  const actions = declaredActions(entry).length;
  if (actions) parts.push(plural(actions, 'action'));
  return parts.join(' · ');
}

/** Why a workspace may not check a row it does not hold. */
function outsideReason(bound: SetParts, row: SetRow, catalog: SetCatalog): string {
  if (row.kind === 'module' && coverage(bound, row, catalog) === 'some') {
    return 'The organization has only part of this module: pick its items.';
  }
  return 'Not in the organization’s set: add it to the organization first.';
}

function Mark({ shown, label }: { shown: Coverage; label: string }) {
  const words = shown === 'all' ? 'included' : shown === 'some' ? 'partly included' : 'not included';
  return (
    <span className="sets-matrix-mark" role="img" aria-label={`${label}: ${words}`}>
      {shown === 'all' && <Check size={14} />}
      {shown === 'some' && <Minus size={14} />}
    </span>
  );
}

/**
 * One organization's sets as a matrix: columns are the organization, then each of its
 * workspaces; rows are the modules (each expandable to its agents, apps, workflows, pipelines
 * and declared actions), then the features. A column the API marks `editable` has checkboxes
 * and its own Save, Discard and Reset to everything; the others only show what they hold.
 * A workspace is offered only what its organization has.
 */
export function SetsMatrix({
  api,
  catalog,
  organization,
  onChange,
  highlightWorkspace = null,
}: {
  api: IamAdminApi;
  catalog: SetCatalog;
  organization: OrganizationSetView;
  /** The organization as the API answered a save. */
  onChange: (organization: OrganizationSetView) => void;
  /** A workspace column to scroll to and highlight. */
  highlightWorkspace?: string | null;
}) {
  const [drafts, setDrafts] = useState<Record<string, SetParts>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState('');
  const root = useRef<HTMLDivElement>(null);

  const columns: Column[] = useMemo(
    () => [
      {
        key: 'org',
        kind: 'organization',
        id: organization.id,
        name: organization.name,
        view: organization,
        bound: null,
      },
      ...organization.workspaces.map(
        (workspace): Column => ({
          key: workspace.id,
          kind: 'workspace',
          id: workspace.id,
          name: workspace.name,
          view: workspace,
          bound: organization.effective,
        }),
      ),
    ],
    [organization],
  );

  useEffect(() => {
    if (!highlightWorkspace) return;
    const header = [...(root.current?.querySelectorAll<HTMLElement>('[data-sets-column]') ?? [])].find(
      (element) => element.dataset.setsColumn === highlightWorkspace,
    );
    header?.scrollIntoView?.({ block: 'nearest', inline: 'center' });
  }, [highlightWorkspace, organization.workspaces.length]);

  const partsOf = (column: Column): SetParts => drafts[column.key] ?? column.view.set;

  const setDraft = (column: Column, next: SetParts) => {
    setDrafts((current) => {
      const copy = { ...current };
      if (sameParts(next, column.view.set)) delete copy[column.key];
      else copy[column.key] = next;
      return copy;
    });
    setErrors((current) => ({ ...current, [column.key]: '' }));
  };

  const edit = (column: Column, row: SetRow, on: boolean) =>
    setDraft(column, toggleRow(partsOf(column), row, on, catalog, column.bound));

  const resetPart = (column: Column, part: Part) => setDraft(column, { ...partsOf(column), [part]: null });

  const discard = (column: Column) => setDraft(column, column.view.set);

  const save = async (column: Column) => {
    const draft = drafts[column.key];
    if (!draft) return;
    setSaving((current) => ({ ...current, [column.key]: true }));
    setErrors((current) => ({ ...current, [column.key]: '' }));
    try {
      if (column.kind === 'organization') {
        onChange(await api.putOrganizationSet(organization.id, draft));
      } else {
        const workspace = await api.putWorkspaceSet(organization.id, column.id, draft);
        onChange({
          ...organization,
          workspaces: organization.workspaces.map((w) => (w.id === workspace.id ? workspace : w)),
        });
      }
      setDrafts((current) => {
        const copy = { ...current };
        delete copy[column.key];
        return copy;
      });
    } catch (e) {
      const message = e instanceof Error && e.message ? e.message : 'Could not save.';
      setErrors((current) => ({ ...current, [column.key]: message }));
    } finally {
      setSaving((current) => ({ ...current, [column.key]: false }));
    }
  };

  const toggleExpanded = (moduleId: string) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(moduleId)) next.delete(moduleId);
      else next.add(moduleId);
      return next;
    });

  const visibleModules = catalog.modules.filter((entry) => moduleMatches(entry, filter));

  const cellClass = (column: Column, extra: (string | false)[] = []) =>
    [
      'sets-matrix-cell',
      column.kind === 'organization' && 'sets-matrix-cell-organization',
      highlightWorkspace === column.id && column.kind === 'workspace' && 'sets-matrix-cell-highlight',
      ...extra,
    ]
      .filter(Boolean)
      .join(' ');

  const cell = (column: Column, row: SetRow, label: string) => {
    const parts = partsOf(column);
    const shown = displayCoverage(parts, column.bound, row, catalog);
    const before = displayCoverage(column.view.set, column.bound, row, catalog);
    const outside = rowOutside(parts, column.bound, row, catalog);
    const within = withinBound(column.bound, row, catalog);
    const changed = shown !== before;
    const className = cellClass(column, [outside && 'sets-matrix-cell-outside', changed && 'sets-matrix-cell-changed']);
    const name = `${label} in ${column.name}`;

    if (!column.view.editable) {
      return (
        <td key={column.key} className={className} title={outside ? NOT_IN_ORGANIZATION : undefined}>
          <Mark shown={shown} label={name} />
        </td>
      );
    }
    // A partly held module: checking holds it whole, when the organization has all of it.
    const next = shown === 'all' ? false : within;
    const blocked = shown === 'none' && !within;
    const title = outside
      ? NOT_IN_ORGANIZATION
      : blocked && column.bound
        ? outsideReason(column.bound, row, catalog)
        : undefined;
    return (
      <td key={column.key} className={className} title={title}>
        <input
          type="checkbox"
          className="sets-matrix-check"
          checked={shown === 'all'}
          ref={(element) => {
            if (element) element.indeterminate = shown === 'some';
          }}
          disabled={blocked || saving[column.key]}
          onChange={() => edit(column, row, next)}
          aria-label={name}
        />
      </td>
    );
  };

  const groupRow = (part: Part, label: string) => (
    <tr className="sets-matrix-row-group">
      <th scope="rowgroup" className="sets-matrix-label sets-matrix-group-label">
        {label}
      </th>
      {columns.map((column) => {
        const parts = partsOf(column);
        const recordsNothing = parts[part] === null;
        const summary = partSummary(parts, part, catalog);
        return (
          <td key={column.key} className={cellClass(column, ['sets-matrix-group-cell'])}>
            <span
              className="sets-matrix-group-summary"
              title={
                recordsNothing && column.kind === 'workspace'
                  ? 'Nothing recorded: everything the organization has'
                  : recordsNothing
                    ? 'Nothing recorded: everything'
                    : undefined
              }
            >
              {summary}
            </span>
            {column.view.editable && !recordsNothing && (
              <button
                type="button"
                className="sets-matrix-link-button"
                onClick={() => resetPart(column, part)}
                disabled={saving[column.key]}
                aria-label={`Reset the ${part} of ${column.name} to everything`}
              >
                Everything
              </button>
            )}
          </td>
        );
      })}
    </tr>
  );

  const header = (column: Column) => {
    const parts = partsOf(column);
    const dirty = !!drafts[column.key];
    const outside = outsideOfBound(parts, column.bound, catalog);
    const busy = !!saving[column.key];
    const highlighted = column.kind === 'workspace' && highlightWorkspace === column.id;
    return (
      <th
        key={column.key}
        scope="col"
        data-sets-column={column.id}
        className={[
          'sets-matrix-col',
          column.kind === 'organization' && 'sets-matrix-col-organization',
          highlighted && 'sets-matrix-col-highlight',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <div className="sets-matrix-col-head">
          <span className="sets-matrix-col-kind">
            {column.kind === 'organization' ? 'Organization' : 'Workspace'}
          </span>
          <span className="sets-matrix-col-name" title={column.name}>
            {column.name}
          </span>
          {!column.view.editable && <span className="sets-matrix-col-tag">Read only</span>}
          {outside.length > 0 && (
            <span className="sets-matrix-col-warning" title={outside.join(', ')}>
              {plural(outside.length, 'entry')} not in the organization’s set
            </span>
          )}
          {column.view.editable && (
            <div className="sets-matrix-col-actions">
              {dirty && (
                <>
                  <button
                    type="button"
                    className="sets-matrix-button sets-matrix-button-primary"
                    onClick={() => void save(column)}
                    disabled={busy}
                    aria-label={`Save ${column.name}`}
                  >
                    {busy ? 'Saving…' : 'Save'}
                  </button>
                  <button
                    type="button"
                    className="sets-matrix-button"
                    onClick={() => discard(column)}
                    disabled={busy}
                    aria-label={`Discard the changes to ${column.name}`}
                  >
                    Discard
                  </button>
                </>
              )}
              {!sameParts(parts, EVERYTHING) && (
                <button
                  type="button"
                  className="sets-matrix-link-button"
                  onClick={() => setDraft(column, EVERYTHING)}
                  disabled={busy}
                  title={
                    column.kind === 'workspace'
                      ? 'Record nothing: the workspace has everything its organization has'
                      : 'Record nothing: the organization has everything'
                  }
                >
                  Reset to everything
                </button>
              )}
            </div>
          )}
          {errors[column.key] && (
            <p className="sets-matrix-col-error" role="alert">
              {errors[column.key]}
            </p>
          )}
        </div>
      </th>
    );
  };

  const blankCells = (className: string) =>
    columns.map((column) => <td key={column.key} className={cellClass(column, [className])} />);

  return (
    <div className="sets-matrix" ref={root}>
      <div className="sets-matrix-toolbar">
        <input
          type="search"
          className="sets-matrix-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filter modules, agents, apps..."
          aria-label="Filter modules"
        />
        <span className="sets-matrix-legend">
          <span className="sets-matrix-legend-outside">Struck through</span>: recorded, but not in the
          organization’s set.
        </span>
      </div>
      <div className="sets-matrix-scroll">
        <table className="sets-matrix-table">
          <thead>
            <tr>
              <th scope="col" className="sets-matrix-label sets-matrix-corner">
                {organization.name}
              </th>
              {columns.map(header)}
            </tr>
          </thead>
          <tbody>
            {groupRow('modules', 'Modules')}
            {catalog.modules.length === 0 && (
              <tr>
                <td className="sets-matrix-empty" colSpan={columns.length + 1}>
                  No module is installed.
                </td>
              </tr>
            )}
            {catalog.modules.length > 0 && visibleModules.length === 0 && (
              <tr>
                <td className="sets-matrix-empty" colSpan={columns.length + 1}>
                  No module matches the filter.
                </td>
              </tr>
            )}
            {visibleModules.map((entry) => {
              const open = expanded.has(entry.module);
              const counts = moduleCounts(entry);
              const actions = entry.declared?.actions ?? [];
              return (
                <Fragment key={entry.module}>
                  <tr className="sets-matrix-row-module">
                    <th scope="row" className="sets-matrix-label">
                      <div className="sets-matrix-module-label">
                      <button
                        type="button"
                        className="sets-matrix-expand"
                        onClick={() => toggleExpanded(entry.module)}
                        aria-expanded={open}
                        aria-label={`${open ? 'Collapse' : 'Expand'} ${entry.module}`}
                        disabled={!counts}
                      >
                        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </button>
                      <span className="sets-matrix-module">
                        <span className="sets-matrix-module-name">{entry.module}</span>
                        {counts && <span className="sets-matrix-module-counts">{counts}</span>}
                      </span>
                      </div>
                    </th>
                    {columns.map((column) => cell(column, { kind: 'module', module: entry.module }, entry.module))}
                  </tr>
                  {open &&
                    ITEM_TYPES.map(({ type, label }) => {
                      const items = itemsOf(entry, type);
                      if (!items.length) return null;
                      return (
                        <Fragment key={type}>
                          <tr className="sets-matrix-row-type">
                            <th scope="rowgroup" className="sets-matrix-label sets-matrix-type-label">
                              {label}
                            </th>
                            {blankCells('sets-matrix-cell-blank')}
                          </tr>
                          {items.map((item) => (
                            <tr key={item.name} className="sets-matrix-row-item">
                              <th scope="row" className="sets-matrix-label sets-matrix-item-label">
                                <span className="sets-matrix-item-name">{item.display_name || item.name}</span>
                                {item.display_name && item.display_name !== item.name && (
                                  <code className="sets-matrix-item-id">{item.name}</code>
                                )}
                              </th>
                              {columns.map((column) =>
                                cell(
                                  column,
                                  { kind: 'item', module: entry.module, type, name: item.name },
                                  `${entry.module} ${type} ${item.name}`,
                                ),
                              )}
                            </tr>
                          ))}
                        </Fragment>
                      );
                    })}
                  {open && actions.length > 0 && (
                    <>
                      <tr className="sets-matrix-row-type">
                        <th scope="rowgroup" className="sets-matrix-label sets-matrix-type-label">
                          Actions
                        </th>
                        {blankCells('sets-matrix-cell-blank')}
                      </tr>
                      {actions.map((action) => (
                        <tr key={action.action} className="sets-matrix-row-item">
                          <th
                            scope="row"
                            className="sets-matrix-label sets-matrix-item-label"
                            title={action.description || undefined}
                          >
                            <code className="sets-matrix-item-name">{action.action}</code>
                            <span className="sets-matrix-item-id">{action.level}</span>
                          </th>
                          {columns.map((column) =>
                            cell(column, { kind: 'action', module: entry.module, action: action.action }, action.action),
                          )}
                        </tr>
                      ))}
                    </>
                  )}
                </Fragment>
              );
            })}
            {groupRow('features', 'Features')}
            {catalog.features.map((feature) => (
              <tr key={feature} className="sets-matrix-row-feature">
                <th scope="row" className="sets-matrix-label sets-matrix-item-label">
                  <span className="sets-matrix-item-name">{featureLabel(feature)}</span>
                  {featureLabel(feature) !== feature && <code className="sets-matrix-item-id">{feature}</code>}
                </th>
                {columns.map((column) =>
                  cell(column, { kind: 'feature', feature }, `Feature ${featureLabel(feature)}`),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
