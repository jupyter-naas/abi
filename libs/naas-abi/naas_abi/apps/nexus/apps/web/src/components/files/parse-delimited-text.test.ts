import { describe, expect, it } from 'vitest';
import { parseDelimitedText } from './parse-delimited-text';

describe('parseDelimitedText', () => {
  it('parses csv with headers and quoted commas', () => {
    const table = parseDelimitedText('name,city\n"Ada, Lovelace",London\nGrace,NYC\n');
    expect(table.headers).toEqual(['name', 'city']);
    expect(table.rows).toEqual([
      ['Ada, Lovelace', 'London'],
      ['Grace', 'NYC'],
    ]);
    expect(table.truncated).toBe(false);
  });

  it('detects tabs for tsv', () => {
    const table = parseDelimitedText('a\tb\n1\t2\n');
    expect(table.headers).toEqual(['a', 'b']);
    expect(table.rows).toEqual([['1', '2']]);
  });

  it('truncates large bodies', () => {
    const lines = ['h1,h2', ...Array.from({ length: 600 }, (_, i) => `${i},x`)];
    const table = parseDelimitedText(lines.join('\n'), { maxRows: 100 });
    expect(table.rows).toHaveLength(100);
    expect(table.totalRows).toBe(600);
    expect(table.truncated).toBe(true);
  });
});
