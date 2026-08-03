'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { buildFinancialClose, closeRecords } from '@/lib/comptabilite/financialClose/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { AccountBarChart } from '@/components/dashboard/viz/AccountBarChart';
import { CompositionDonut } from '@/components/dashboard/viz/CompositionDonut';
import { CloseProgress } from '@/components/dashboard/comptabilite/financial-close/CloseProgress';
import { GanttTimeline } from '@/components/dashboard/comptabilite/financial-close/GanttTimeline';
import { DataTable } from '@/components/dashboard/table/DataTable';
import type { DataTableColumn } from '@/components/dashboard/table/DataTable';

const integerFormatter = new Intl.NumberFormat('fr-FR', {
  maximumFractionDigits: 0,
});

const daysFormatter = new Intl.NumberFormat('fr-FR', {
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 0,
});

const PAGE_HINT =
  'The close checklist for the latest month in the selected period: what is done, what is still running, what is blocking it, and what the close has turned up.';

const TASK_COLUMNS: DataTableColumn[] = [
  { key: 'task_label', label: 'Task' },
  { key: 'area', label: 'Area' },
  { key: 'owner', label: 'Owner' },
  { key: 'planned', label: 'Planned' },
  { key: 'planned_end_date', label: 'Due' },
  { key: 'actual_end_date', label: 'Completed' },
  { key: 'status', label: 'Status' },
  {
    key: 'days_late',
    label: 'Late (d)',
    align: 'right',
    valueStyle: 'decimal',
    maximumFractionDigits: 0,
  },
  { key: 'validated', label: 'Validated' },
  { key: 'validator', label: 'Validated by' },
];

export function FinancialCloseSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => closeRecords(datasets.financial_close),
    [datasets.financial_close],
  );
  const view = useMemo(() => buildFinancialClose(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const taskRows = useMemo(
    () =>
      view.tasks.map((task) => ({
        task_label: task.task_label,
        area: task.area_label,
        owner: task.owner,
        planned: `D${task.planned_start_day}–D${task.planned_end_day}`,
        planned_end_date: task.planned_end_date,
        actual_end_date: task.actual_end_date || '—',
        status: task.status_label,
        days_late: task.days_late,
        validated: task.is_validated ? 'Yes' : 'No',
        validator: task.validator || '—',
      })),
    [view.tasks],
  );

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Financial Close{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No close checklist for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Financial Close{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          {view.asOfLabel} close · {kpis.taskCount} tasks across {view.areas.length}{' '}
          areas ·{' '}
          {view.isOpen
            ? view.progressDay !== null
              ? `open, day ${view.progressDay} of ${kpis.plannedDuration}`
              : 'open, not started'
            : 'books locked'}
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Completion Rate"
          value={kpis.completion}
          valueStyle="percent"
          percentInput="rate"
          maximumFractionDigits={0}
          tone={
            // A close that has not started is not behind — a month whose books
            // are still open and untouched reads neutral, not red.
            view.isOpen && kpis.doneTasks === 0
              ? 'default'
              : kpis.completion >= 1
                ? 'success'
                : kpis.completion >= 0.5
                  ? 'warning'
                  : 'danger'
          }
          subtitle={`${kpis.doneTasks} of ${kpis.taskCount} tasks done`}
          hint={`Share of the ${view.asOfLabel} checklist signed off. A close is a per-month exercise, so this reads the latest month in the window rather than averaging across it.`}
        />
        <KpiCard
          label="Remaining Tasks"
          value={kpis.remainingTasks}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={kpis.remainingTasks === 0 ? 'success' : 'warning'}
          subtitle={`${kpis.blockedTasks} blocked`}
          hint="Tasks not yet done — running, blocked or not started. Blocked ones need a decision before they can move."
        />
        <KpiCard
          label="Late Tasks"
          value={kpis.lateTasks}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={
            kpis.lateTasks === 0
              ? 'success'
              : kpis.lateTasks > kpis.taskCount * 0.2
                ? 'danger'
                : 'warning'
          }
          subtitle="Past their planned day"
          hint="Tasks that overran the business day they were planned to finish on, plus anything still open past its due day."
        />
        <KpiCard
          label="Open Issues"
          value={kpis.openIssues}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={
            kpis.openIssues === 0
              ? 'success'
              : kpis.highIssues > 0
                ? 'danger'
                : 'warning'
          }
          subtitle={`${kpis.highIssues} high severity · ${kpis.issueCount} raised`}
          hint="Issues the close turned up and has not resolved. Counted across the whole window — a locked month leaves none behind, so anything here belongs to a close still running."
        />
        <KpiCard
          label="Close Duration"
          value={kpis.closeDuration ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={1}
          displayValue={
            kpis.closeDuration === null
              ? '—'
              : `${daysFormatter.format(kpis.closeDuration)} d`
          }
          tone={
            kpis.closeDuration === null
              ? 'default'
              : kpis.closeDuration <= kpis.plannedDuration
                ? 'success'
                : 'warning'
          }
          subtitle={`Plan ${kpis.plannedDuration} business days`}
          hint="Mean business day the last task landed, across the months in the window that actually closed. Undefined while nothing in the window has closed yet."
        />
        <KpiCard
          label="Validated Tasks"
          value={kpis.validatedTasks}
          valueStyle="decimal"
          maximumFractionDigits={0}
          tone={
            kpis.validationRate === null
              ? 'default'
              : kpis.validationRate >= 0.9
                ? 'success'
                : 'warning'
          }
          subtitle={
            kpis.validationRate !== null
              ? `${percentFormatter.format(kpis.validationRate)} of completed tasks`
              : 'Reviewed and signed off'
          }
          hint="Completed tasks a second pair of eyes has signed off. Doing the work and having it reviewed are two different controls."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CloseProgress
          title="Close Progress"
          hint={`Where the ${view.asOfLabel} close stands, area by area, worst first.`}
          areas={view.areas}
        />
        <CompositionDonut
          title="Task Status"
          hint={`Every task on the ${view.asOfLabel} checklist, counted once at the state it is in.`}
          totalLabel="Tasks"
          formatValue={(value) => integerFormatter.format(value)}
          slices={view.statuses
            .filter((status) => status.count > 0)
            .map((status) => ({
              key: status.key,
              label: status.label,
              value: status.count,
            }))}
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4">
        <GanttTimeline
          title="Gantt Timeline"
          hint={`The ${view.asOfLabel} close plan against what actually happened, in business days after the period end.`}
          tasks={view.tasks}
          progressDay={view.progressDay}
        />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AccountBarChart
          title="Issue Distribution"
          hint="Issues raised by the closes in the selected period, by area. Where they cluster is where the month-end process leaks."
          items={view.issueAreas.map((area) => ({
            key: area.key,
            label: area.label,
            value: area.count,
          }))}
          valueStyle="decimal"
          visibleCount={5}
          color="var(--recovery-orange)"
          captionFor={(item) => {
            const area = view.issueAreas.find((entry) => entry.key === item.key);
            if (!area) return null;
            return `${area.open} still open · ${area.high} high severity`;
          }}
          emptyMessage="No issues raised for this perimeter."
        />
        <div className="glass h-full rounded-lg p-6">
          <h3
            className="type-title-5 mb-4 cursor-help"
            title="Issues raised by the closes in the selected period, most recent first."
          >
            Close Issues
          </h3>
          {view.issues.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)]">
              No issues raised for this perimeter.
            </p>
          ) : (
            <ul className="max-h-[21rem] space-y-2 overflow-y-auto overscroll-contain pr-1 scrollbar-thin">
              {view.issues.slice(0, 40).map((issue) => (
                <li
                  key={issue.task_ref}
                  className="flex items-start gap-2 border-b border-[var(--border)] pb-2 last:border-0"
                >
                  <span
                    className="mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full"
                    style={{
                      backgroundColor:
                        issue.severity === 'high'
                          ? 'var(--recovery-danger)'
                          : issue.severity === 'medium'
                            ? 'var(--recovery-orange)'
                            : 'var(--text-muted)',
                    }}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium" title={issue.title}>
                      {issue.title}
                    </p>
                    <p className="text-xs text-[var(--text-muted)]">
                      {issue.area_label} · {issue.owner} · raised {issue.raised_date}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 text-xs font-semibold ${
                      issue.is_resolved
                        ? 'text-[var(--recovery-success)]'
                        : 'text-[var(--recovery-orange)]'
                    }`}
                  >
                    {issue.status_label}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ---- Checklist ------------------------------------------------------ */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint={`The ${view.asOfLabel} checklist, in the order the close runs it.`}
        >
          Closing Checklist
        </PageTitle>
      </div>

      <DataTable
        records={taskRows}
        columns={TASK_COLUMNS}
        emptyMessage="No close checklist for this perimeter."
        paginate
        defaultPageSize={20}
        globalSearch
        globalSearchPlaceholder="Search a task, area or owner…"
        exportable
        exportFileName="closing-checklist"
      />

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        The checklist, the progress bars and the readiness KPIs read the{' '}
        {view.asOfLabel} close — the last month in the selected period. Close
        Duration and the issue distribution span the whole window, because both
        only mean something over a run of months.
      </p>
    </div>
  );
}
