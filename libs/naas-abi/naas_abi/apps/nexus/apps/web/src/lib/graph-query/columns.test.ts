import { describe, expect, it } from 'vitest'
import {
  defaultOperator,
  discoveredToColumn,
  discoveredToColumns,
  expandedColumn,
  operatorsFor,
  sanitizeColumnId,
  sourceForDiscovered,
} from './columns'
import type { DiscoveredColumn } from './types'

function dc(partial: Partial<DiscoveredColumn>): DiscoveredColumn {
  return {
    id: 'label',
    predicate_uri: 'http://www.w3.org/2000/01/rdf-schema#label',
    label: 'label',
    kind: 'property',
    direction: 'out',
    datatype: 'string',
    datatype_source: 'data',
    source: 'both',
    instance_count: 10,
    is_functional: true,
    facetable: true,
    target_classes: [],
    ...partial,
  }
}

describe('sanitizeColumnId', () => {
  it('keeps word characters and replaces the rest', () => {
    expect(sanitizeColumnId('has_chunks')).toBe('has_chunks')
    expect(sanitizeColumnId('foo-bar.baz')).toBe('foo_bar_baz')
    expect(sanitizeColumnId('a##b')).toBe('a_b')
  })
  it('collapses repeats and trims edges', () => {
    expect(sanitizeColumnId('__a__b__')).toBe('a_b')
  })
  it('falls back to col for empty/garbage', () => {
    expect(sanitizeColumnId('***')).toBe('col')
    expect(sanitizeColumnId('')).toBe('col')
  })
})

describe('operatorsFor / defaultOperator', () => {
  it('offers contains-first for strings, comparison for numbers', () => {
    expect(operatorsFor('string')[0]).toBe('contains')
    expect(defaultOperator('number')).toBe('eq')
    expect(operatorsFor('iri')).toContain('is')
    expect(operatorsFor('boolean')).toEqual(['eq', 'neq', 'isEmpty', 'isNotEmpty'])
  })
})

describe('sourceForDiscovered', () => {
  it('maps a data property to a zero-hop property source', () => {
    const src = sourceForDiscovered(dc({ kind: 'property', predicate_uri: 'http://ex/age' }))
    expect(src).toEqual({ kind: 'property', predicate: 'http://ex/age', path: [] })
  })
  it('maps a relation to a single-hop node source honoring direction', () => {
    const src = sourceForDiscovered(
      dc({ kind: 'relation', predicate_uri: 'http://ex/hasChat', direction: 'out' }),
    )
    expect(src).toEqual({
      kind: 'node',
      path: [{ predicate: 'http://ex/hasChat', direction: 'out', quantifier: 'one' }],
      show: 'label',
    })
  })
})

describe('discoveredToColumn', () => {
  it('forces datatype iri for relations', () => {
    const col = discoveredToColumn(dc({ kind: 'relation', datatype: 'string', id: 'hasChat' }))
    expect(col.datatype).toBe('iri')
    expect(col.source.kind).toBe('node')
  })
  it('preserves inferred datatype for properties', () => {
    const col = discoveredToColumn(dc({ kind: 'property', datatype: 'number', id: 'age' }))
    expect(col.datatype).toBe('number')
    expect(col.id).toBe('age')
  })
})

describe('discoveredToColumns', () => {
  it('de-duplicates ids deterministically while keeping order', () => {
    const cols = discoveredToColumns([
      dc({ id: 'name', predicate_uri: 'http://a/name' }),
      dc({ id: 'name', predicate_uri: 'http://b/name' }),
      dc({ id: 'name', predicate_uri: 'http://c/name' }),
    ])
    expect(cols.map((c) => c.id)).toEqual(['name', 'name_1', 'name_2'])
  })
})

describe('expandedColumn', () => {
  const relation = dc({ id: 'extracted_by', predicate_uri: 'http://x/extracted_by', label: 'extracted by', kind: 'relation', datatype: 'iri' })
  it('builds a 2-hop property column through the relation', () => {
    const field = dc({ id: 'model_name', predicate_uri: 'http://x/model_name', label: 'model', kind: 'property', datatype: 'string' })
    const col = expandedColumn(relation, field)
    expect(col.id).toBe('extracted_by_model_name') // sanitize collapses the double underscore
    expect(col.datatype).toBe('string')
    expect(col.source).toEqual({
      kind: 'property',
      predicate: 'http://x/model_name',
      path: [{ predicate: 'http://x/extracted_by', direction: 'out', quantifier: 'one' }],
    })
  })
  it('builds a 2-hop node column when the field is itself a relation', () => {
    const field = dc({ id: 'used', predicate_uri: 'http://x/used', kind: 'relation', datatype: 'iri' })
    const col = expandedColumn(relation, field)
    expect(col.datatype).toBe('iri')
    expect(col.source).toEqual({
      kind: 'node',
      show: 'label',
      path: [
        { predicate: 'http://x/extracted_by', direction: 'out', quantifier: 'one' },
        { predicate: 'http://x/used', direction: 'out', quantifier: 'one' },
      ],
    })
  })
})
