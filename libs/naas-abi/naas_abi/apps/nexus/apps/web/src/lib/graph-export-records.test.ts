import { describe, expect, it } from 'vitest';
import {
  EXPORT_RETENTION_MS,
  pruneExportRecords,
  type ExportRecord,
} from './graph-export-records';

function makeRecord(createdAt: string): ExportRecord {
  return {
    id: '1',
    graphUri: 'http://example.org/g',
    graphLabel: 'Graph',
    workspaceId: 'ws-1',
    format: 'ttl',
    status: 'ready',
    createdAt,
  };
}

describe('pruneExportRecords', () => {
  it('keeps records from the last 7 days', () => {
    const now = Date.parse('2026-06-09T12:00:00.000Z');
    const records = [
      makeRecord('2026-06-08T12:00:00.000Z'),
      makeRecord('2026-06-02T12:00:00.000Z'),
      makeRecord('2026-06-01T11:59:59.999Z'),
    ];

    expect(pruneExportRecords(records, now)).toHaveLength(2);
  });

  it('uses a 7-day retention window', () => {
    expect(EXPORT_RETENTION_MS).toBe(7 * 24 * 60 * 60 * 1000);
  });
});
