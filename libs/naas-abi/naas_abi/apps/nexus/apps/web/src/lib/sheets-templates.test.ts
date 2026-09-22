import { describe, expect, it } from 'vitest';

import {
  SHEETS_HOME_BLANK_TEMPLATE_ID,
  sheetsHomeTemplateCards,
  sheetsTemplateMenuRows,
} from './sheets-templates';

describe('sheetsHomeTemplateCards', () => {
  it('puts Blank first and skips the blank seed from the catalog list', () => {
    const cards = sheetsHomeTemplateCards([
      { id: 'abi/grid-light-v1', name: 'Blank' },
      { id: 'abi/monthly-pnl-v1', name: 'Monthly P&L' },
      { id: 'abi/budget-vs-actuals-v1', name: 'Budget vs Actuals' },
      { id: 'abi/cash-runway-v1', name: 'Cash Runway' },
    ]);
    expect(cards.map((card) => card.label)).toEqual([
      'Blank',
      'Monthly P&L',
      'Budget vs Actuals',
      'Cash Runway',
    ]);
    expect(cards[0]).toEqual({
      id: SHEETS_HOME_BLANK_TEMPLATE_ID,
      label: 'Blank',
      blank: true,
    });
  });
});

describe('sheetsTemplateMenuRows', () => {
  it('lists human catalog names without source prefixes', () => {
    const rows = sheetsTemplateMenuRows([
      { id: 'abi/monthly-pnl-v1', source: 'abi', name: 'Monthly P&L' },
      { id: 'abi/cash-runway-v1', source: 'abi', name: 'Cash Runway' },
    ]);
    expect(rows).toEqual([
      { kind: 'template', id: 'abi/monthly-pnl-v1', label: 'Monthly P&L', swatch: undefined },
      { kind: 'template', id: 'abi/cash-runway-v1', label: 'Cash Runway', swatch: undefined },
    ]);
  });
});
