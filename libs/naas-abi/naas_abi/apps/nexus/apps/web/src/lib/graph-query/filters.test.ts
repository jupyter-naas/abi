import { describe, expect, it } from 'vitest'
import {
  andAll,
  buildFilterTree,
  coerceScalar,
  columnFilterToNode,
  conditionToNode,
  isBlank,
  isValidCondition,
  selectionToNode,
  sourceFilterToNode,
} from './filters'
import type { ColumnSource, Datatype, FilterCondition } from './types'

describe('coerceScalar', () => {
  it('parses numbers, leaving bad input untouched', () => {
    expect(coerceScalar('42', 'number')).toBe(42)
    expect(coerceScalar('  3.5 ', 'number')).toBe(3.5)
    expect(coerceScalar('abc', 'number')).toBe('abc')
  })
  it('parses booleans case-insensitively', () => {
    expect(coerceScalar('TRUE', 'boolean')).toBe(true)
    expect(coerceScalar('false', 'boolean')).toBe(false)
    expect(coerceScalar('maybe', 'boolean')).toBe('maybe')
  })
  it('passes strings/dates/iris through', () => {
    expect(coerceScalar('2026-01-01', 'date')).toBe('2026-01-01')
    expect(coerceScalar('http://x', 'iri')).toBe('http://x')
  })
})

describe('isValidCondition', () => {
  it('accepts nullary operators with no value', () => {
    expect(isValidCondition('isEmpty', null)).toBe(true)
    expect(isValidCondition('isNotEmpty', undefined as never)).toBe(true)
  })
  it('requires a 2-tuple for between', () => {
    expect(isValidCondition('between', [1, 10])).toBe(true)
    expect(isValidCondition('between', [1])).toBe(false)
    expect(isValidCondition('between', [1, ''])).toBe(false)
  })
  it('requires a non-empty array for in/notIn', () => {
    expect(isValidCondition('in', ['a'])).toBe(true)
    expect(isValidCondition('in', [])).toBe(false)
  })
  it('requires a scalar for ordinary operators', () => {
    expect(isValidCondition('contains', 'x')).toBe(true)
    expect(isValidCondition('contains', '')).toBe(false)
    expect(isValidCondition('eq', ['a'])).toBe(false)
  })
})

describe('conditionToNode', () => {
  it('drops the value for nullary operators', () => {
    expect(conditionToNode('c', 'string', 'isEmpty', 'ignored')).toEqual({
      op: 'cond',
      target: { kind: 'column', column_id: 'c' },
      operator: 'isEmpty',
      value: null,
    })
  })
  it('coerces number values', () => {
    const node = conditionToNode('age', 'number', 'gte', '30') as FilterCondition
    expect(node.value).toBe(30)
  })
  it('coerces between bounds element-wise', () => {
    const node = conditionToNode('age', 'number', 'between', ['10', '20']) as FilterCondition
    expect(node.value).toEqual([10, 20])
  })
  it('returns null for incomplete conditions', () => {
    expect(conditionToNode('c', 'string', 'contains', '')).toBeNull()
    expect(conditionToNode('c', 'number', 'between', ['10'])).toBeNull()
  })
})

describe('selectionToNode', () => {
  it('produces an in condition over the selected values', () => {
    expect(selectionToNode('city', ['Paris', 'Berlin'])).toEqual({
      op: 'cond',
      target: { kind: 'column', column_id: 'city' },
      operator: 'in',
      value: ['Paris', 'Berlin'],
    })
  })
  it('is null when nothing selected', () => {
    expect(selectionToNode('city', [])).toBeNull()
  })
})

describe('columnFilterToNode', () => {
  it('is null when blank', () => {
    expect(isBlank(undefined)).toBe(true)
    expect(isBlank({ selected: [] })).toBe(true)
    expect(columnFilterToNode('c', 'string', { selected: [] })).toBeNull()
  })
  it('ANDs selection and condition when both present', () => {
    const node = columnFilterToNode('city', 'string', {
      selected: ['Paris'],
      operator: 'contains',
      value: 'ar',
    })
    expect(node).toEqual({
      op: 'and',
      children: [
        { op: 'cond', target: { kind: 'column', column_id: 'city' }, operator: 'in', value: ['Paris'] },
        { op: 'cond', target: { kind: 'column', column_id: 'city' }, operator: 'contains', value: 'ar' },
      ],
    })
  })
  it('returns a single node when only one side is present', () => {
    const node = columnFilterToNode('age', 'number', { operator: 'gt', value: '5' })
    expect(node).toEqual({
      op: 'cond',
      target: { kind: 'column', column_id: 'age' },
      operator: 'gt',
      value: 5,
    })
  })
})

describe('sourceFilterToNode', () => {
  const source: ColumnSource = {
    kind: 'property',
    predicate: 'http://x/path',
    path: [{ predicate: 'http://x/has_item', direction: 'in', quantifier: 'one' }],
  }
  it('targets the inline source instead of a column id', () => {
    expect(sourceFilterToNode(source, 'string', { operator: 'contains', value: 'pubmed' })).toEqual({
      op: 'cond',
      target: { kind: 'source', source },
      operator: 'contains',
      value: 'pubmed',
    })
  })
  it('is null when the state is blank', () => {
    expect(sourceFilterToNode(source, 'string', undefined)).toBeNull()
  })
})

describe('andAll / buildFilterTree', () => {
  it('flattens to null/single/group', () => {
    expect(andAll([null, null])).toBeNull()
    const single = { op: 'cond', target: { kind: 'column', column_id: 'a' }, operator: 'eq', value: 1 } as const
    expect(andAll([null, single])).toEqual(single)
    expect(andAll([single, single])).toEqual({ op: 'and', children: [single, single] })
  })
  it('builds an AND tree across columns, coercing by datatype', () => {
    const datatypes: Record<string, Datatype> = { age: 'number', city: 'string' }
    const tree = buildFilterTree(
      {
        age: { operator: 'gte', value: '21' },
        city: { selected: ['Paris'] },
        empty: { selected: [] },
      },
      datatypes,
    )
    expect(tree).toEqual({
      op: 'and',
      children: [
        { op: 'cond', target: { kind: 'column', column_id: 'age' }, operator: 'gte', value: 21 },
        { op: 'cond', target: { kind: 'column', column_id: 'city' }, operator: 'in', value: ['Paris'] },
      ],
    })
  })
})
