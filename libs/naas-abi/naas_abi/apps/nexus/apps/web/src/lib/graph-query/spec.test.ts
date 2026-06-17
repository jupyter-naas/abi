import { describe, expect, it } from 'vitest'
import {
  aggregateSpecErrors,
  anchorFor,
  buildAggregateSpec,
  buildListSpec,
  isRunnable,
  listSpecErrors,
  type AggregateDraft,
  type ListDraft,
} from './spec'
import type { Column } from './types'

const cols: Column[] = [
  { id: 'label', datatype: 'string', source: { kind: 'property', predicate: 'http://x/label', path: [] } },
  { id: 'age', datatype: 'number', source: { kind: 'property', predicate: 'http://x/age', path: [] } },
]

function listDraft(over: Partial<ListDraft> = {}): ListDraft {
  return {
    graphUris: ['http://g/ws'],
    classUris: ['http://x/Person'],
    columns: cols,
    filters: {},
    sort: [],
    ...over,
  }
}

describe('anchorFor', () => {
  it('prefers an instances anchor when instance uris are present', () => {
    expect(anchorFor(['http://x/Person'], ['http://x/alice'])).toEqual({
      kind: 'instances',
      instance_uris: ['http://x/alice'],
    })
  })
  it('falls back to a class anchor', () => {
    expect(anchorFor(['http://x/Person'])).toEqual({ kind: 'class', class_uris: ['http://x/Person'] })
  })
})

describe('buildListSpec', () => {
  it('assembles a runnable list spec with no filters', () => {
    const spec = buildListSpec(listDraft())
    expect(spec.mode).toBe('list')
    expect(spec.version).toBe(1)
    expect(spec.root).toEqual({ kind: 'class', class_uris: ['http://x/Person'] })
    expect(spec.columns).toHaveLength(2)
    expect(spec.filters).toBeNull()
    expect(isRunnable(spec)).toBe(true)
  })

  it('folds per-column filters into the tree', () => {
    const spec = buildListSpec(
      listDraft({ filters: { age: { operator: 'gt', value: '30' } } }),
    )
    expect(spec.filters).toEqual({
      op: 'cond',
      target: { kind: 'column', column_id: 'age' },
      operator: 'gt',
      value: 30,
    })
  })

  it('does not mutate the draft columns array', () => {
    const draft = listDraft()
    const spec = buildListSpec(draft)
    spec.columns[0].label = 'changed'
    expect(draft.columns[0].label).toBeUndefined()
  })
})

describe('listSpecErrors', () => {
  it('is empty for a valid spec', () => {
    expect(listSpecErrors(buildListSpec(listDraft()))).toEqual([])
  })
  it('flags missing graphs, columns, anchor', () => {
    const errs = listSpecErrors(
      buildListSpec(listDraft({ graphUris: [], classUris: [], columns: [] })),
    )
    expect(errs).toContain('Select at least one graph.')
    expect(errs).toContain('Pick at least one class to anchor the rows.')
    expect(errs).toContain('Add at least one column.')
  })
  it('flags a sort referencing an unknown column', () => {
    const spec = buildListSpec(listDraft({ sort: [{ column_id: 'nope', direction: 'asc' }] }))
    expect(listSpecErrors(spec)).toContain('Sort references unknown column "nope".')
  })
})

describe('buildAggregateSpec', () => {
  function aggDraft(over: Partial<AggregateDraft> = {}): AggregateDraft {
    return {
      graphUris: ['http://g/ws'],
      classUris: ['http://x/ExtractedItem'],
      groupBy: [{ id: 'paper', show_kind: 'property', show_predicate: 'http://x/path' }],
      measures: [{ id: 'items', fn: 'count' }],
      filters: {},
      filterDatatypes: {},
      sort: [],
      ...over,
    }
  }
  it('assembles a runnable aggregate spec', () => {
    const spec = buildAggregateSpec(aggDraft())
    expect(spec.mode).toBe('aggregate')
    expect(spec.fact).toEqual({ kind: 'class', class_uris: ['http://x/ExtractedItem'] })
    expect(spec.group_by).toHaveLength(1)
    expect(spec.measures).toHaveLength(1)
    expect(aggregateSpecErrors(spec)).toEqual([])
  })
  it('flags missing group-by and measures', () => {
    const spec = buildAggregateSpec(aggDraft({ groupBy: [], measures: [] }))
    const errs = aggregateSpecErrors(spec)
    expect(errs).toContain('Add at least one group-by dimension.')
    expect(errs).toContain('Add at least one measure.')
  })
})
