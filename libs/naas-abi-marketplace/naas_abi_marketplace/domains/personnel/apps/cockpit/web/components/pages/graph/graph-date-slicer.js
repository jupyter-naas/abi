/**
 * Temporal region filter with start/end date inputs (ISO YYYY-MM-DD).
 */

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function clampIsoDate(value, min, max) {
  if (!value) return value;
  if (min && value < min) return min;
  if (max && value > max) return max;
  return value;
}

/** Parse and validate an ISO calendar date (YYYY-MM-DD). */
export function normalizeIsoDate(value) {
  if (!value) return null;
  const trimmed = String(value).trim().slice(0, 10);
  if (!ISO_DATE_RE.test(trimmed)) return null;
  const [year, month, day] = trimmed.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
  return trimmed;
}

export function resolveSelectedRange(selectedStart, selectedEnd, globalRange) {
  const min = globalRange?.min || null;
  const max = globalRange?.max || null;
  let start = selectedStart || min;
  let end = selectedEnd || max;
  start = clampIsoDate(start, min, max);
  end = clampIsoDate(end, min, max);
  if (start && end && start > end) {
    end = max || end;
  }
  return { start, end, min, max };
}

export function isFullRange(selectedStart, selectedEnd, globalRange) {
  const { start, end, min, max } = resolveSelectedRange(
    selectedStart,
    selectedEnd,
    globalRange
  );
  return Boolean(min && max && start === min && end === max);
}

/** Collect process roots that carry temporal bounds in a visible graph set. */
export function collectProcessTemporalRecords(visible, { isProcessRoot }) {
  const byId = new Map();
  const add = (record) => {
    if (!record || !isProcessRoot(record)) return;
    if (!record.startedAt && !record.endedAt) return;
    byId.set(record.id, record);
  };
  for (const record of visible.processes || []) add(record);
  for (const record of visible.entities || []) add(record);
  return [...byId.values()];
}

export function computeGlobalDateRange(processes) {
  let min = null;
  let max = null;
  for (const process of processes) {
    const start = process.startedAt || null;
    const end = process.endedAt || todayIso();
    if (start && (!min || start < min)) min = start;
    if (end && (!max || end > max)) max = end;
  }
  return { min, max };
}

export function processOverlapsRange(process, rangeStart, rangeEnd) {
  const start = process.startedAt;
  if (!start) return false;
  const end = process.endedAt || todayIso();
  return start <= rangeEnd && end >= rangeStart;
}

export function filterToFocusRootOnly(visible, focusRootId) {
  const focusPerson = (visible.people || []).find((person) => person.id === focusRootId);
  if (focusPerson) {
    return { people: [focusPerson], entities: [], processes: [], relations: [] };
  }
  const focusEntity = (visible.entities || []).find((entity) => entity.id === focusRootId);
  if (focusEntity) {
    return { people: [], entities: [focusEntity], processes: [], relations: [] };
  }
  const focusProcess = (visible.processes || []).find((process) => process.id === focusRootId);
  if (focusProcess) {
    return { people: [], entities: [], processes: [focusProcess], relations: [] };
  }
  return { people: [], entities: [], processes: [], relations: [] };
}

export function applyDateFilter(
  visible,
  selectedStart,
  selectedEnd,
  globalRange,
  focusRootId,
  helpers
) {
  if (isFullRange(selectedStart, selectedEnd, globalRange)) return visible;

  const { start, end } = resolveSelectedRange(selectedStart, selectedEnd, globalRange);
  if (!start || !end) return visible;

  const allProcesses = helpers.visibleProcessOptions(visible);
  const hiddenProcessIds = new Set();
  for (const process of allProcesses) {
    const record = helpers.findProcessRecord(visible, process.id);
    if (!record?.startedAt || !processOverlapsRange(record, start, end)) {
      hiddenProcessIds.add(process.id);
    }
  }

  if (hiddenProcessIds.size === allProcesses.length) {
    return filterToFocusRootOnly(visible, focusRootId);
  }

  return helpers.applyProcessFilter(
    visible,
    hiddenProcessIds,
    new Set(),
    focusRootId,
    { strict: true }
  );
}

export function configureDateSlicer(config = {}) {
  return {
    storageKey: config.storage_key || "cockpit-graph-date-slicer",
  };
}

export function readStoredDateSlicer(storageKey) {
  try {
    const stored = JSON.parse(sessionStorage.getItem(storageKey) || "{}");
    const rangeStart =
      typeof stored.rangeStart === "string" ? stored.rangeStart.slice(0, 10) : null;
    const rangeEnd =
      typeof stored.rangeEnd === "string" ? stored.rangeEnd.slice(0, 10) : null;
    return { rangeStart, rangeEnd };
  } catch {
    return { rangeStart: null, rangeEnd: null };
  }
}

export function persistDateSlicer(storageKey, rangeStart, rangeEnd) {
  sessionStorage.setItem(
    storageKey,
    JSON.stringify({
      rangeStart,
      rangeEnd,
    })
  );
}

export function renderDateSlicer({ esc, globalRange, selectedStart, selectedEnd }) {
  const { start, end, min, max } = resolveSelectedRange(selectedStart, selectedEnd, globalRange);
  const hasRange = Boolean(min && max);
  const bounds = hasRange ? ` min="${esc(min)}" max="${esc(max)}"` : "";

  return `<div class="graph-date-slicer" id="graph-date-slicer">
    <span class="graph-date-slicer-label">Temporal Region</span>
    <div class="graph-date-slicer-fields">
      <label class="graph-date-field">
        <span class="graph-date-field-label">From</span>
        <input type="text" class="graph-date-input" id="graph-date-start" value="${esc(start || "")}" placeholder="YYYY-MM-DD" spellcheck="false" autocomplete="off"${bounds} aria-label="From date (YYYY-MM-DD)">
      </label>
      <label class="graph-date-field">
        <span class="graph-date-field-label">To</span>
        <input type="text" class="graph-date-input" id="graph-date-end" value="${esc(end || "")}" placeholder="YYYY-MM-DD" spellcheck="false" autocomplete="off"${bounds} aria-label="To date (YYYY-MM-DD)">
      </label>
    </div>
  </div>`;
}

/** Wire start/end date inputs; repaints on change. */
export function mountDateRangeSlicer(root, { onRangeChange } = {}) {
  if (!root) return () => {};

  const startInput = root.querySelector("#graph-date-start");
  const endInput = root.querySelector("#graph-date-end");
  if (!startInput || !endInput) return () => {};

  let lastStart = startInput.value || null;
  let lastEnd = endInput.value || null;

  const commitInput = (input, previous) => {
    const min = input.getAttribute("min") || null;
    const max = input.getAttribute("max") || null;
    let value = normalizeIsoDate(input.value);
    if (!value) {
      input.value = previous || "";
      return previous || null;
    }
    value = clampIsoDate(value, min, max);
    input.value = value;
    return value;
  };

  const commit = () => {
    lastStart = commitInput(startInput, lastStart);
    lastEnd = commitInput(endInput, lastEnd);
    onRangeChange?.(lastStart, lastEnd);
  };

  startInput.addEventListener("change", commit);
  endInput.addEventListener("change", commit);
  startInput.addEventListener("blur", commit);
  endInput.addEventListener("blur", commit);

  return () => {
    startInput.removeEventListener("change", commit);
    endInput.removeEventListener("change", commit);
    startInput.removeEventListener("blur", commit);
    endInput.removeEventListener("blur", commit);
  };
}
