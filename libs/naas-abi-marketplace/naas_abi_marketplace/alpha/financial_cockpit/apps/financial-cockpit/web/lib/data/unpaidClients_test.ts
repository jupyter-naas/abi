import {
  aggregateRecoveryActionKpis,
  aggregateUnpaidClientsDataset,
  buildUnpaidSummary,
  computeRecoveryAction,
  filterInvoiceTableRecords,
  filterTrackedInvoiceRecords,
  isLateStatusInvoiceRecord,
  isUnpaidInvoiceRecord,
  recoveryActionForRecord,
  type UnpaidClientsDataset,
  type UnpaidInvoiceRecord,
} from '@/lib/data/unpaidClients';

describe('computeRecoveryAction', () => {
  it('returns empty when due date is missing', () => {
    expect(computeRecoveryAction(undefined, 10)).toBe('');
    expect(computeRecoveryAction('', 10)).toBe('');
  });

  it('applies phone / formal notice / arbitration thresholds', () => {
    expect(computeRecoveryAction('2026-01-01', 0)).toBe('');
    expect(computeRecoveryAction('2026-01-01', 3)).toBe('Relance Pennylane');
    expect(computeRecoveryAction('2026-01-01', 13)).toBe('Relance Pennylane');
    expect(computeRecoveryAction('2026-01-01', 14)).toBe('Relance Téléphonique');
    expect(computeRecoveryAction('2026-01-01', 20)).toBe('Relance Téléphonique');
    expect(computeRecoveryAction('2026-01-01', 21)).toBe('Mise en demeure');
    expect(computeRecoveryAction('2026-01-01', 29)).toBe('Mise en demeure');
    expect(computeRecoveryAction('2026-01-01', 30)).toBe('Arbitrage');
  });
});

describe('isUnpaidInvoiceRecord', () => {
  it('accepts late/partially_paid with remaining TTC and rejects others', () => {
    expect(
      isUnpaidInvoiceRecord({
        invoice_id: '1',
        client: 'A',
        site: 'S1',
        status: 'partially_paid',
        status_label: 'Partiellement payé',
        amount_ht: 40000,
        amount_ttc: 48000,
        remaining_amount_ttc: 24000,
        remaining_amount_ht: 20000,
        days_overdue: 5,
      }),
    ).toBe(true);

    expect(
      isUnpaidInvoiceRecord({
        invoice_id: '2',
        client: 'B',
        site: 'S2',
        status: 'paid',
        status_label: 'Payé',
        amount_ht: 100,
        amount_ttc: 120,
        remaining_amount_ttc: 120,
        remaining_amount_ht: 100,
        days_overdue: 0,
        is_unpaid: false,
      }),
    ).toBe(false);
  });
});

describe('isLateStatusInvoiceRecord', () => {
  it('includes late/partially_paid even when remaining balance is zero', () => {
    expect(
      isLateStatusInvoiceRecord({
        invoice_id: '1',
        client: 'A',
        site: 'S1',
        status: 'partially_paid',
        status_label: 'Partiellement payé',
        amount_ht: 100,
        amount_ttc: 120,
        remaining_amount_ttc: 0,
        remaining_amount_ht: 0,
        days_overdue: 0,
        is_unpaid: false,
      }),
    ).toBe(true);

    expect(
      isLateStatusInvoiceRecord({
        invoice_id: '2',
        client: 'B',
        site: 'S2',
        status: 'paid',
        status_label: 'Payé',
        amount_ht: 100,
        amount_ttc: 120,
        remaining_amount_ttc: 0,
        remaining_amount_ht: 0,
        days_overdue: 0,
      }),
    ).toBe(false);
  });
});

describe('aggregateRecoveryActionKpis', () => {
  const records: UnpaidInvoiceRecord[] = [
    {
      invoice_id: '1',
      client: 'A',
      site: 'S1',
      status: 'late',
      status_label: 'En retard',
      amount_ht: 100,
      amount_ttc: 120,
      remaining_amount_ttc: 120,
      remaining_amount_ht: 100,
      days_overdue: 3,
      due_date: '2026-01-01',
      is_unpaid: true,
    },
    {
      invoice_id: '2',
      client: 'B',
      site: 'S2',
      status: 'late',
      status_label: 'En retard',
      amount_ht: 200,
      amount_ttc: 240,
      remaining_amount_ttc: 240,
      remaining_amount_ht: 200,
      days_overdue: 15,
      due_date: '2026-01-01',
      is_unpaid: true,
    },
    {
      invoice_id: '3',
      client: 'C',
      site: 'S3',
      status: 'late',
      status_label: 'En retard',
      amount_ht: 300,
      amount_ttc: 360,
      remaining_amount_ttc: 360,
      remaining_amount_ht: 300,
      days_overdue: 22,
      due_date: '2026-01-01',
      is_unpaid: true,
    },
    {
      invoice_id: '4',
      client: 'D',
      site: 'S4',
      status: 'late',
      status_label: 'En retard',
      amount_ht: 400,
      amount_ttc: 480,
      remaining_amount_ttc: 480,
      remaining_amount_ht: 400,
      days_overdue: 35,
      due_date: '2026-01-01',
      is_unpaid: true,
    },
  ];

  it('aggregates total unpaid and escalation buckets', () => {
    const kpis = aggregateRecoveryActionKpis(records);

    expect(kpis.en_cours).toEqual({ amount: 1200, count: 4 });
    expect(kpis.relance_telephonique).toEqual({ amount: 240, count: 1 });
    expect(kpis.mise_en_demeure).toEqual({ amount: 360, count: 1 });
    expect(kpis.arbitrage).toEqual({ amount: 480, count: 1 });
  });

  it('prefers persisted recovery_action when present', () => {
    expect(
      recoveryActionForRecord({
        ...records[0],
        recovery_action: 'Arbitrage',
      }),
    ).toBe('Arbitrage');
  });
});

describe('aggregateUnpaidClientsDataset', () => {
  const trackedRecords: UnpaidInvoiceRecord[] = [
    {
      invoice_id: '1',
      client: 'A',
      site: 'S1',
      status: 'late',
      status_label: 'En retard',
      amount_ht: 1000,
      amount_ttc: 1200,
      remaining_amount_ttc: 1200,
      remaining_amount_ht: 1000,
      days_overdue: 3,
      scenario: '2026-01',
      scenario_year: '2026',
      is_unpaid: true,
    },
    {
      invoice_id: '2',
      client: 'B',
      site: 'S2',
      status: 'paid',
      status_label: 'Payé',
      amount_ht: 500,
      amount_ttc: 600,
      remaining_amount_ttc: 0,
      remaining_amount_ht: 0,
      days_overdue: 0,
      scenario: '2026-02',
      scenario_year: '2026',
      is_unpaid: false,
    },
    {
      invoice_id: '3',
      client: 'C',
      site: 'S3',
      status: 'partially_paid',
      status_label: 'Partiellement payé',
      amount_ht: 4000,
      amount_ttc: 4800,
      remaining_amount_ttc: 0,
      remaining_amount_ht: 0,
      days_overdue: 0,
      is_unpaid: false,
    },
  ];

  it('recomputes summary KPIs from tracked records and keeps all allowed invoices', () => {
    const dataset: UnpaidClientsDataset = {
      schema_version: '1.0',
      data_version: '2026-07-01',
      summary: {
        invoiced_amount_ttc: 0,
        unpaid_amount_ttc: 0,
        collected_amount_ttc: 0,
        recovery_rate: 0,
        unpaid_invoice_count: 0,
        invoice_count: 0,
      },
      aging_buckets: [],
      by_customer: [],
      records: trackedRecords,
    };

    const aggregated = aggregateUnpaidClientsDataset(dataset);

    expect(aggregated.summary.invoiced_amount_ttc).toBe(6600);
    expect(aggregated.summary.unpaid_amount_ttc).toBe(1200);
    expect(aggregated.summary.recovery_rate).toBe(0.8182);
    expect(aggregated.summary.invoice_count).toBe(3);
    expect(aggregated.records).toHaveLength(3);
    expect(aggregated.records.map((row) => row.invoice_id)).toEqual(['1', '2', '3']);
  });
});

describe('filterInvoiceTableRecords', () => {
  it('defaults to late and partially_paid statuses', () => {
    const records: UnpaidInvoiceRecord[] = [
      {
        invoice_id: '1',
        client: 'A',
        site: 'S1',
        status: 'late',
        status_label: 'En retard',
        amount_ht: 100,
        amount_ttc: 120,
        remaining_amount_ttc: 120,
        remaining_amount_ht: 100,
        days_overdue: 5,
      },
      {
        invoice_id: '2',
        client: 'B',
        site: 'S2',
        status: 'paid',
        status_label: 'Payé',
        amount_ht: 200,
        amount_ttc: 240,
        remaining_amount_ttc: 0,
        remaining_amount_ht: 0,
        days_overdue: 0,
      },
      {
        invoice_id: '3',
        client: 'C',
        site: 'S3',
        status: 'partially_paid',
        status_label: 'Partiellement payé',
        amount_ht: 300,
        amount_ttc: 360,
        remaining_amount_ttc: 0,
        remaining_amount_ht: 0,
        days_overdue: 0,
      },
    ];

    expect(filterInvoiceTableRecords(records).map((row) => row.invoice_id)).toEqual([
      '1',
      '3',
    ]);
    expect(filterInvoiceTableRecords(records, 'all').map((row) => row.invoice_id)).toEqual([
      '1',
      '2',
      '3',
    ]);
  });
});

describe('buildUnpaidSummary', () => {
  it('recomputes portfolio KPIs after scenario filtering', () => {
    const records: UnpaidInvoiceRecord[] = [
      {
        invoice_id: '1',
        client: 'A',
        site: 'S1',
        status: 'late',
        status_label: 'En retard',
        amount_ht: 1000,
        amount_ttc: 1200,
        remaining_amount_ttc: 1200,
        remaining_amount_ht: 1000,
        days_overdue: 3,
        scenario: '2026-01',
        scenario_year: '2026',
        is_unpaid: true,
      },
      {
        invoice_id: '2',
        client: 'B',
        site: 'S2',
        status: 'paid',
        status_label: 'Payé',
        amount_ht: 500,
        amount_ttc: 600,
        remaining_amount_ttc: 0,
        remaining_amount_ht: 0,
        days_overdue: 0,
        scenario: '2026-02',
        scenario_year: '2026',
        is_unpaid: false,
      },
    ];

    const january = filterTrackedInvoiceRecords(records).filter(
      (record) => record.scenario === '2026-01',
    );

    expect(buildUnpaidSummary(january)).toEqual({
      invoiced_amount_ttc: 1200,
      unpaid_amount_ttc: 1200,
      collected_amount_ttc: 0,
      recovery_rate: 0,
      unpaid_invoice_count: 1,
      invoice_count: 1,
    });
  });

  it('includes allowed statuses outside the legacy FILTER_STATUS whitelist', () => {
    const summary = buildUnpaidSummary([
      {
        invoice_id: '1',
        client: 'A',
        site: 'S1',
        status: 'validated',
        status_label: 'Validée',
        amount_ht: 750,
        amount_ttc: 900,
        remaining_amount_ttc: 0,
        remaining_amount_ht: 0,
        days_overdue: 0,
        is_unpaid: false,
      },
      {
        invoice_id: '2',
        client: 'B',
        site: 'S2',
        status: 'late',
        status_label: 'En retard',
        amount_ht: 1000,
        amount_ttc: 1200,
        remaining_amount_ttc: 1200,
        remaining_amount_ht: 1000,
        days_overdue: 3,
        is_unpaid: true,
      },
    ]);

    expect(summary.invoiced_amount_ttc).toBe(2100);
    expect(summary.unpaid_amount_ttc).toBe(1200);
    expect(summary.collected_amount_ttc).toBe(900);
    expect(summary.recovery_rate).toBe(0.4286);
    expect(summary.invoice_count).toBe(2);
  });
});
