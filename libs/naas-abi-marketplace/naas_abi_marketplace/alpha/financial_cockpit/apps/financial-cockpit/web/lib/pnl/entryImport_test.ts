import {
  guessPnlEntryColumnMapping,
  parseAmountValue,
  parseMonthValue,
  parsePnlImportRows,
  resolveFamilleValue,
  validPnlImportRows,
} from '@/lib/pnl/entryImport';

describe('guessPnlEntryColumnMapping', () => {
  it('maps common French and English headers', () => {
    const mapping = guessPnlEntryColumnMapping([
      'Company',
      'Thirdparty',
      'Famille_2',
      'Categorie_2',
      'Date',
      'Amount',
    ]);
    expect(mapping.company).toBe('Company');
    expect(mapping.thirdparty).toBe('Thirdparty');
    expect(mapping.famille_2).toBe('Famille_2');
    expect(mapping.month).toBe('Date');
    expect(mapping.amount).toBe('Amount');
  });
});

describe('parseMonthValue', () => {
  it('accepts YYYY-MM and common variants', () => {
    expect(parseMonthValue('2026-03')).toBe('2026-03');
    expect(parseMonthValue('2026-03-15')).toBe('2026-03');
    expect(parseMonthValue('03/2026')).toBe('2026-03');
    expect(parseMonthValue('2026/3')).toBe('2026-03');
  });
});

describe('parseAmountValue', () => {
  it('parses French and plain numbers', () => {
    expect(parseAmountValue('1 234,56')).toBe(1234.56);
    expect(parseAmountValue('1500')).toBe(1500);
    expect(parseAmountValue('€-250')).toBe(-250);
  });
});

describe('resolveFamilleValue', () => {
  it('matches known famille labels loosely', () => {
    expect(resolveFamilleValue('2.Ventes')).toBe('2.Ventes');
    expect(resolveFamilleValue('ventes')).toBe('2.Ventes');
  });
});

describe('parsePnlImportRows', () => {
  const orgOptions = [{ slug: '5_blanche', label: '5 Blanche' }];

  it('returns valid rows when mapping and values are correct', () => {
    const parsed = parsePnlImportRows(
      [
        {
          Société: '5 Blanche',
          Tiers: 'Fournisseur A',
          Famille: '2.Ventes',
          'Cat 2': 'CA',
          Date: '2026-04',
          Montant: '1200',
        },
      ],
      {
        company: 'Société',
        thirdparty: 'Tiers',
        famille_2: 'Famille',
        categorie_2: 'Cat 2',
        month: 'Date',
        amount: 'Montant',
      },
      orgOptions,
      { includeCategorie3: true },
    );

    const valid = validPnlImportRows(parsed);
    expect(valid).toHaveLength(1);
    expect(valid[0].organization_slug).toBe('5_blanche');
    expect(valid[0].month).toBe('2026-04');
    expect(valid[0].amount).toBe(1200);
  });
});
