'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ArrowDown, ArrowLeft, ArrowUp, Plus, Trash2, X } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { Popover } from '@/components/database-view/primitives';
import {
  BOARD_PALETTE,
  DONE_STAGE,
  INBOX_STAGE,
  WEEKDAY_NAMES,
  boardPath,
  boardSettingsPath,
  type BoardChoice,
  type BoardColor,
  type BoardSettings,
} from '@/lib/board';
import { useBoardStore } from '@/stores/board';
import { BoardMenuBar } from '../components/board-menu-bar';
import '../board.css';

type Draft = Pick<
  BoardSettings,
  'iteration_weeks' | 'iteration_start_day' | 'stages' | 'priorities' | 'default_stage' | 'suggested_labels'
>;

const toDraft = (settings: BoardSettings): Draft => ({
  iteration_weeks: settings.iteration_weeks,
  iteration_start_day: settings.iteration_start_day,
  stages: settings.stages.map((c) => ({ ...c })),
  priorities: settings.priorities.map((c) => ({ ...c })),
  default_stage: settings.default_stage,
  suggested_labels: [...settings.suggested_labels],
});

function ColorPicker({
  value,
  disabled,
  onChange,
}: {
  value: BoardColor;
  disabled: boolean;
  onChange: (color: BoardColor) => void;
}) {
  return (
    <Popover
      width="w-44"
      trigger={({ toggle }) => (
        <button
          type="button"
          className={`board-swatch board-dot-${value}`}
          title={`Color: ${value}`}
          aria-label={`Color: ${value}`}
          disabled={disabled}
          onClick={toggle}
        />
      )}
    >
      {(close) => (
        <div className="board-settings-swatches" role="radiogroup" aria-label="Color">
          {BOARD_PALETTE.map((color) => (
            <button
              key={color}
              type="button"
              role="radio"
              aria-checked={color === value}
              title={color}
              aria-label={color}
              className={`board-swatch board-dot-${color}`}
              onClick={() => {
                onChange(color);
                close();
              }}
            />
          ))}
        </div>
      )}
    </Popover>
  );
}

/**
 * Ordered stages or priorities. ``locked`` keys (Inbox, Done) cannot move or
 * go; ``fixedEnds`` keeps the first and last rows where they are.
 */
function ChoiceList({
  title,
  description,
  noun,
  choices,
  locked,
  fixedEnds,
  disabled,
  onChange,
}: {
  title: string;
  description: string;
  noun: string;
  choices: BoardChoice[];
  locked: string[];
  fixedEnds: boolean;
  disabled: boolean;
  onChange: (choices: BoardChoice[]) => void;
}) {
  const update = (index: number, patch: Partial<BoardChoice>) =>
    onChange(choices.map((c, i) => (i === index ? { ...c, ...patch } : c)));
  const move = (index: number, delta: number) => {
    const next = [...choices];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    onChange(next);
  };
  const first = fixedEnds ? 1 : 0;
  const last = fixedEnds ? choices.length - 2 : choices.length - 1;
  const add = () => {
    const fresh: BoardChoice = { key: '', label: `New ${noun}`, color: 'slate' };
    // New stages go before Done; new priorities at the end.
    onChange(fixedEnds ? [...choices.slice(0, -1), fresh, choices[choices.length - 1]] : [...choices, fresh]);
  };

  return (
    <section className="board-settings-section">
      <div>
        <h2 className="board-settings-title">{title}</h2>
        <p className="board-settings-hint">{description}</p>
      </div>
      <ol className="board-settings-list">
        {choices.map((choice, index) => {
          const isLocked = locked.includes(choice.key);
          return (
            <li key={`${choice.key}-${index}`} className="board-settings-row">
              <ColorPicker value={choice.color} disabled={disabled} onChange={(color) => update(index, { color })} />
              <input
                className="board-drawer-input"
                value={choice.label}
                maxLength={40}
                disabled={disabled}
                aria-label={`${noun} name`}
                onChange={(e) => update(index, { label: e.target.value })}
              />
              {isLocked && <span className="board-settings-badge">System</span>}
              <span className="board-settings-row-actions">
                <button
                  type="button"
                  className="board-icon-button"
                  title="Move up"
                  disabled={disabled || isLocked || index <= first}
                  onClick={() => move(index, -1)}
                >
                  <ArrowUp size={13} />
                </button>
                <button
                  type="button"
                  className="board-icon-button"
                  title="Move down"
                  disabled={disabled || isLocked || index >= last}
                  onClick={() => move(index, 1)}
                >
                  <ArrowDown size={13} />
                </button>
                <button
                  type="button"
                  className="board-icon-button"
                  title={isLocked ? `${choice.label} is required` : `Remove ${noun}`}
                  disabled={disabled || isLocked || choices.length <= 1}
                  onClick={() => onChange(choices.filter((_, i) => i !== index))}
                >
                  <Trash2 size={13} />
                </button>
              </span>
            </li>
          );
        })}
      </ol>
      <button type="button" className="board-column-add board-column-add-inline" disabled={disabled} onClick={add}>
        <Plus size={12} /> Add {noun}
      </button>
    </section>
  );
}

function LabelEditor({
  labels,
  disabled,
  onChange,
}: {
  labels: string[];
  disabled: boolean;
  onChange: (labels: string[]) => void;
}) {
  const [draft, setDraft] = useState('');
  const add = () => {
    const value = draft.split(/\s+/).join(' ').trim();
    setDraft('');
    if (value && !labels.includes(value)) onChange([...labels, value]);
  };
  return (
    <div className="board-drawer-chips">
      {labels.map((label) => (
        <span key={label} className="board-drawer-chip">
          {label}
          {!disabled && (
            <button
              type="button"
              className="board-drawer-chip-remove"
              title={`Remove ${label}`}
              onClick={() => onChange(labels.filter((l) => l !== label))}
            >
              <X size={11} />
            </button>
          )}
        </span>
      ))}
      {!disabled && (
        <input
          className="board-drawer-chip-input"
          value={draft}
          maxLength={40}
          placeholder="Add a label, then Enter"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              add();
            }
          }}
          onBlur={add}
        />
      )}
    </div>
  );
}

export default function BoardSettingsPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const router = useRouter();
  const { load, loaded, settings, error, saveSettings, clearError } = useBoardStore();
  const [draft, setDraft] = useState<Draft>(() => toDraft(settings));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (workspaceId) void load(workspaceId, { force: true });
  }, [workspaceId, load]);
  // Start from the stored settings once loaded (and after each save).
  useEffect(() => setDraft(toDraft(settings)), [settings]);

  const disabled = !settings.can_edit || saving;
  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(toDraft(settings)), [draft, settings]);
  const set = (patch: Partial<Draft>) => {
    setSaved(false);
    setDraft((d) => ({ ...d, ...patch }));
  };

  const save = async () => {
    setSaving(true);
    clearError();
    try {
      await saveSettings(draft);
      setSaved(true);
    } catch {
      // Shown in the error banner.
    } finally {
      setSaving(false);
    }
  };

  const triagedStages = draft.stages.filter((s) => s.key !== INBOX_STAGE);

  return (
    <div className="board-page">
      <Header
        title="Board settings"
        subtitle="Iterations, stages, priorities and labels of this workspace's board"
        nav={
          <BoardMenuBar
            onNewTask={() => router.push(boardPath(workspaceId, { newTask: true }))}
            onSettings={() => router.push(boardSettingsPath(workspaceId))}
          />
        }
      />
      {error && (
        <div className="board-error" role="alert">
          <span>{error}</span>
          <button type="button" className="board-error-dismiss" title="Dismiss" onClick={clearError}>
            <X size={12} />
          </button>
        </div>
      )}
      {loaded && !settings.can_edit && (
        <div className="board-notice" role="status">
          <span>Only workspace owners and admins can change these settings.</span>
        </div>
      )}

      <div className="board-page-scroll">
        <div className="board-settings">
          <Link href={boardPath(workspaceId)} className="board-settings-back">
            <ArrowLeft size={13} /> Back to the board
          </Link>

          <section className="board-settings-section">
            <div>
              <h2 className="board-settings-title">Iterations</h2>
              <p className="board-settings-hint">
                A change applies from the end of the current iteration; existing iterations keep their dates.
              </p>
            </div>
            <div className="board-drawer-fields">
              <label className="board-drawer-label" htmlFor="board-settings-weeks">Length</label>
              <select
                id="board-settings-weeks"
                className="board-drawer-select"
                value={draft.iteration_weeks}
                disabled={disabled}
                onChange={(e) => set({ iteration_weeks: Number(e.target.value) })}
              >
                {[1, 2, 3, 4].map((weeks) => (
                  <option key={weeks} value={weeks}>
                    {weeks} {weeks === 1 ? 'week' : 'weeks'}
                  </option>
                ))}
              </select>
              <label className="board-drawer-label" htmlFor="board-settings-start">Starts on</label>
              <select
                id="board-settings-start"
                className="board-drawer-select"
                value={draft.iteration_start_day}
                disabled={disabled}
                onChange={(e) => set({ iteration_start_day: Number(e.target.value) })}
              >
                {WEEKDAY_NAMES.map((name, index) => (
                  <option key={name} value={index}>{name}</option>
                ))}
              </select>
            </div>
          </section>

          <ChoiceList
            title="Stages"
            description="Board columns, in order. Inbox (triage) and Done are required; add your own stages between them. A stage still used by tasks cannot be removed."
            noun="stage"
            choices={draft.stages}
            locked={[INBOX_STAGE, DONE_STAGE]}
            fixedEnds
            disabled={disabled}
            onChange={(stages) =>
              set({
                stages,
                default_stage: stages.some((s) => s.key === draft.default_stage && s.key)
                  ? draft.default_stage
                  : stages[1]?.key || DONE_STAGE,
              })
            }
          />

          <section className="board-settings-section">
            <div>
              <h2 className="board-settings-title">New tasks</h2>
              <p className="board-settings-hint">
                Stage of a task created in an iteration, or moved out of Inbox. Save new stages before picking them.
              </p>
            </div>
            <div className="board-drawer-fields">
              <label className="board-drawer-label" htmlFor="board-settings-default-stage">Starts in</label>
              <select
                id="board-settings-default-stage"
                className="board-drawer-select"
                value={draft.default_stage}
                disabled={disabled}
                onChange={(e) => set({ default_stage: e.target.value })}
              >
                {triagedStages
                  .filter((s) => s.key)
                  .map((stage) => (
                    <option key={stage.key} value={stage.key}>{stage.label}</option>
                  ))}
              </select>
            </div>
          </section>

          <ChoiceList
            title="Priorities"
            description="Most urgent first: sorting and grouping by priority follow this order. A priority still used by tasks cannot be removed."
            noun="priority"
            choices={draft.priorities}
            locked={[]}
            fixedEnds={false}
            disabled={disabled}
            onChange={(priorities) => set({ priorities })}
          />

          <section className="board-settings-section">
            <div>
              <h2 className="board-settings-title">Suggested labels</h2>
              <p className="board-settings-hint">Offered when labelling a task; any other label can still be typed.</p>
            </div>
            <LabelEditor
              labels={draft.suggested_labels}
              disabled={disabled}
              onChange={(suggested_labels) => set({ suggested_labels })}
            />
          </section>

          {settings.can_edit && (
            <div className="board-settings-actions">
              {saved && !dirty && <span className="board-settings-hint">Saved.</span>}
              <button
                type="button"
                className="board-button"
                disabled={!dirty || saving}
                onClick={() => setDraft(toDraft(settings))}
              >
                Discard changes
              </button>
              <button
                type="button"
                className="board-button board-button-primary"
                disabled={!dirty || saving}
                onClick={() => void save()}
              >
                {saving ? 'Saving…' : 'Save settings'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
