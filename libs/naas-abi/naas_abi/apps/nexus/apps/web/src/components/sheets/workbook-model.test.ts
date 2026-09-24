import { describe, expect, it } from 'vitest';
import { columnLabel, parseAddress, patchCells, parseClipboard, copyRange, readWorkbook, renameSheet, writeWorkbook, type Workbook } from './workbook-model';
const model: Workbook = { title: 'Test', sheets: [{ name: 'Inputs', rows: [['001', 5], [null, '=B1*2']] }, { name: 'Summary', rows: [['=Inputs!B2', '=IF(1,"Inputs!B2",0)']] }] };
const html = `<html><script type="application/vnd.nexus.sheet+json">${JSON.stringify(model)}</script><body>Keep me</body></html>`;
describe('workbook editing', () => {
  it('maps Excel column and cell addresses', () => {
    expect([0, 25, 26, 701, 702].map(columnLabel)).toEqual(['A', 'Z', 'AA', 'ZZ', 'AAA']);
    expect(parseAddress('$AA$25')).toEqual({ row: 24, col: 26 });
    expect(parseAddress('A0')).toBeNull();
    expect(parseAddress('XFE1')).toBeNull();
  });
  it('patches empty cells without damaging other tabs or formulas', () => {
    const next = patchCells(model, 0, { row: 4, col: 2 }, [[3, '=B1']]);
    expect(next.sheets[0].rows[4]).toEqual([null, null, 3, '=B1']);
    expect(next.sheets[0].rows[1][1]).toBe('=B1*2');
    expect(next.sheets[1]).toEqual(model.sheets[1]);
    expect(model.sheets[0].rows).toHaveLength(2);
  });
  it('roundtrips HTML-sensitive content and preserves the surrounding document', () => {
    const next = patchCells(model, 0, { row: 0, col: 0 }, [['</script><img src=x>', '$&\\n']]);
    const saved = writeWorkbook(html, next);
    expect(readWorkbook(saved)).toEqual(next);
    expect(saved).toContain('<body>Keep me</body>');
    expect(saved).not.toContain('</script><img');
  });
  it('roundtrips multiline TSV, literal identifiers and formulas', () => {
    const cells = parseClipboard('001\t5\t=SUM(B1:B2)\r\n"two\nlines"\t"a""b"\t\r\n');
    expect(cells).toEqual([['001', 5, '=SUM(B1:B2)'], ['two\nlines', 'a"b', null]]);
    const next = patchCells(model, 0, { row: 0, col: 0 }, cells);
    expect(parseClipboard(copyRange(next, 0, { row: 0, col: 0 }, { row: 1, col: 2 }))).toEqual(cells);
  });
  it('renames references without rewriting quoted strings', () => {
    const next = renameSheet(model, 0, 'My Inputs');
    expect(next.sheets[1].rows[0]).toEqual(["='My Inputs'!B2", '=IF(1,"Inputs!B2",0)']);
    expect(() => renameSheet(model, 0, 'summary')).toThrow('already exists');
    expect(() => renameSheet(model, 0, 'a/b')).toThrow();
  });
});
