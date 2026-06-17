import { describe, expect, it } from 'vitest'
import {
  exploreReducer,
  filtersFromNode,
  initialExploreState,
  MAX_DRILL_DEPTH,
  specFromState,
  stateFromSpec,
  type ExploreState,
} from './explore-state'
import type { Column, ListSpec } from './types'

const col = (id: string): Column => ({
  id,
  datatype: 'string',
  source: { kind: 'property', predicate: `http://x/${id}`, path: [] },
})

function seeded(): ExploreState {
  return {
    ...initialExploreState(),
    graphUris: ['http://g/ws'],
    classUris: ['http://x/Person'],
    columns: [col('a'), col('b'), col('c')],
  }
}

describe('exploreReducer', () => {
  it('resets columns/filters/sort when the anchor class changes', () => {
    const s = exploreReducer(seeded(), { type: 'setClasses', classUris: ['http://x/Other'] })
    expect(s.columns).toEqual([])
    expect(s.filters).toEqual({})
    expect(s.sort).toEqual([])
  })

  it('adds a column idempotently by id', () => {
    let s = seeded()
    s = exploreReducer(s, { type: 'addColumn', column: col('a') })
    expect(s.columns).toHaveLength(3)
    s = exploreReducer(s, { type: 'addColumn', column: col('d') })
    expect(s.columns.map((c) => c.id)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('removing a column drops its filter and sort', () => {
    let s = seeded()
    s = exploreReducer(s, { type: 'setFilter', columnId: 'b', state: { selected: ['x'] } })
    s = exploreReducer(s, { type: 'toggleSort', columnId: 'b' })
    s = exploreReducer(s, { type: 'removeColumn', columnId: 'b' })
    expect(s.columns.map((c) => c.id)).toEqual(['a', 'c'])
    expect(s.filters.b).toBeUndefined()
    expect(s.sort).toEqual([])
  })

  it('moves a column within bounds and ignores out-of-range moves', () => {
    let s = seeded()
    s = exploreReducer(s, { type: 'moveColumn', columnId: 'c', delta: -1 })
    expect(s.columns.map((c) => c.id)).toEqual(['a', 'c', 'b'])
    s = exploreReducer(s, { type: 'moveColumn', columnId: 'a', delta: -1 })
    expect(s.columns.map((c) => c.id)).toEqual(['a', 'c', 'b']) // unchanged
  })

  it('reorders a column to a target index (drag and drop)', () => {
    let s = seeded() // [a, b, c]
    s = exploreReducer(s, { type: 'reorderColumn', columnId: 'a', toIndex: 2 })
    expect(s.columns.map((c) => c.id)).toEqual(['b', 'c', 'a'])
    s = exploreReducer(s, { type: 'reorderColumn', columnId: 'a', toIndex: 0 })
    expect(s.columns.map((c) => c.id)).toEqual(['a', 'b', 'c'])
    s = exploreReducer(s, { type: 'reorderColumn', columnId: 'nope', toIndex: 0 })
    expect(s.columns.map((c) => c.id)).toEqual(['a', 'b', 'c']) // unknown id → unchanged
  })

  it('cycles sort asc → desc → none on repeated toggles', () => {
    let s = seeded()
    s = exploreReducer(s, { type: 'toggleSort', columnId: 'a' })
    expect(s.sort).toEqual([{ column_id: 'a', direction: 'asc' }])
    s = exploreReducer(s, { type: 'toggleSort', columnId: 'a' })
    expect(s.sort).toEqual([{ column_id: 'a', direction: 'desc' }])
    s = exploreReducer(s, { type: 'toggleSort', columnId: 'a' })
    expect(s.sort).toEqual([])
  })

  it('switching sort to a different column starts fresh ascending', () => {
    let s = seeded()
    s = exploreReducer(s, { type: 'toggleSort', columnId: 'a' })
    s = exploreReducer(s, { type: 'toggleSort', columnId: 'b' })
    expect(s.sort).toEqual([{ column_id: 'b', direction: 'asc' }])
  })
})

describe('specFromState', () => {
  it('produces a list spec by default with the filters folded in', () => {
    let s = seeded()
    s = exploreReducer(s, { type: 'setFilter', columnId: 'a', state: { operator: 'contains', value: 'foo' } })
    const spec = specFromState(s) as ListSpec
    expect(spec.mode).toBe('list')
    expect(spec.root).toEqual({ kind: 'class', class_uris: ['http://x/Person'] })
    expect(spec.filters).toEqual({
      op: 'cond',
      target: { kind: 'column', column_id: 'a' },
      operator: 'contains',
      value: 'foo',
    })
  })

  it('prefers an instances anchor when instance uris are set', () => {
    let s = seeded()
    s = exploreReducer(s, { type: 'setInstances', instanceUris: ['http://x/alice'] })
    const spec = specFromState(s) as ListSpec
    expect(spec.root).toEqual({ kind: 'instances', instance_uris: ['http://x/alice'] })
  })

  it('produces an aggregate spec in aggregate mode', () => {
    let s = seeded()
    s = exploreReducer(s, { type: 'setMode', mode: 'aggregate' })
    s = exploreReducer(s, { type: 'setGroupBy', groupBy: [{ id: 'paper', show_kind: 'property', show_predicate: 'p' }] })
    s = exploreReducer(s, { type: 'setMeasures', measures: [{ id: 'n', fn: 'count' }] })
    const spec = specFromState(s)
    expect(spec.mode).toBe('aggregate')
  })
})

describe('filtersFromNode', () => {
  it('decomposes a single column condition', () => {
    expect(
      filtersFromNode({ op: 'cond', target: { kind: 'column', column_id: 'age' }, operator: 'gt', value: 5 }),
    ).toEqual({ age: { operator: 'gt', value: 5 } })
  })
  it('maps an in condition back to a selection', () => {
    expect(
      filtersFromNode({ op: 'cond', target: { kind: 'column', column_id: 'city' }, operator: 'in', value: ['Paris'] }),
    ).toEqual({ city: { selected: ['Paris'] } })
  })
  it('merges an AND of conditions across columns', () => {
    expect(
      filtersFromNode({
        op: 'and',
        children: [
          { op: 'cond', target: { kind: 'column', column_id: 'city' }, operator: 'in', value: ['Paris'] },
          { op: 'cond', target: { kind: 'column', column_id: 'age' }, operator: 'gte', value: 21 },
        ],
      }),
    ).toEqual({ city: { selected: ['Paris'] }, age: { operator: 'gte', value: 21 } })
  })
  it('ignores unsupported or/not trees', () => {
    expect(filtersFromNode({ op: 'not', child: { op: 'cond', target: { kind: 'column', column_id: 'a' }, operator: 'eq', value: 1 } })).toEqual({})
  })
})

describe('drill-down spine', () => {
  const D = 'http://x#'
  function drilled(): ExploreState {
    let s: ExploreState = { ...initialExploreState(), graphUris: ['G'] }
    s = exploreReducer(s, { type: 'setRoot', classUri: D + 'PDFPaperFile', classLabel: 'PDFPaperFile' })
    s = exploreReducer(s, { type: 'setColumns', columns: [col('path')] })
    s = exploreReducer(s, { type: 'setFilter', columnId: 'path', state: { operator: 'contains', value: 'pubmed' } })
    s = exploreReducer(s, {
      type: 'follow',
      via: { predicate: D + 'has_chunks', direction: 'out', label: 'has_chunks' },
      targetClassUri: D + 'Chunk',
      targetClassLabel: 'Chunk',
    })
    s = exploreReducer(s, {
      type: 'follow',
      via: { predicate: D + 'has_extracted_item', direction: 'out', label: 'has_extracted_item' },
      targetClassUri: D + 'ExtractedItem',
      targetClassLabel: 'ExtractedItem',
    })
    return s
  }

  it('following changes the grain and freezes the prior level filters', () => {
    const s = drilled()
    expect(s.spine.map((n) => n.classLabel)).toEqual(['PDFPaperFile', 'Chunk', 'ExtractedItem'])
    expect(s.classUris).toEqual([D + 'ExtractedItem'])
    expect(s.filters).toEqual({}) // grain filters reset
    expect(s.spine[0].filters).toEqual({ path: { operator: 'contains', value: 'pubmed' } }) // frozen on root
  })

  it('carries the selected columns down, re-projected via the inverse path', () => {
    const carried = drilled().columns.find((c) => c.id === 'path')
    expect(carried).toBeDefined()
    expect(carried?.label).toBe('PDFPaperFile · path')
    expect(carried?.source).toEqual({
      kind: 'property',
      predicate: D + 'path',
      path: [
        { predicate: D + 'has_extracted_item', direction: 'in', quantifier: 'one' },
        { predicate: D + 'has_chunks', direction: 'in', quantifier: 'one' },
      ],
    })
  })

  it('lowers the frozen ancestor filter to a grain-level inverse-path condition', () => {
    const spec = specFromState(drilled())
    expect(spec.root).toEqual({ kind: 'class', class_uris: [D + 'ExtractedItem'] })
    expect(spec.filters).toEqual({
      op: 'cond',
      target: {
        kind: 'source',
        source: {
          kind: 'property',
          predicate: D + 'path',
          path: [
            { predicate: D + 'has_extracted_item', direction: 'in', quantifier: 'one' },
            { predicate: D + 'has_chunks', direction: 'in', quantifier: 'one' },
          ],
        },
      },
      operator: 'contains',
      value: 'pubmed',
    })
  })

  it('drilling back to the root restores its frozen filters/columns', () => {
    const back = exploreReducer(drilled(), { type: 'drillTo', index: 0 })
    expect(back.classUris).toEqual([D + 'PDFPaperFile'])
    expect(back.spine).toHaveLength(1)
    expect(back.filters).toEqual({ path: { operator: 'contains', value: 'pubmed' } })
    expect(back.columns.map((c) => c.id)).toEqual(['path'])
  })

  it('drilling to the current grain is a no-op', () => {
    const s = drilled()
    expect(exploreReducer(s, { type: 'drillTo', index: 2 })).toBe(s)
  })

  it('caps the drill depth so cyclic relations cannot drill forever', () => {
    let s: ExploreState = { ...initialExploreState(), graphUris: ['G'] }
    s = exploreReducer(s, { type: 'setRoot', classUri: D + 'A', classLabel: 'A' })
    // Alternate A → B → A → B … past the cap.
    for (let i = 0; i < MAX_DRILL_DEPTH + 3; i++) {
      const to = i % 2 === 0 ? 'B' : 'A'
      s = exploreReducer(s, {
        type: 'follow',
        via: { predicate: D + 'rel', direction: 'out', label: 'rel' },
        targetClassUri: D + to,
        targetClassLabel: to,
      })
    }
    expect(s.spine.length).toBe(MAX_DRILL_DEPTH)
  })
})

describe('stateFromSpec round-trip', () => {
  it('preserves a simple list builder state', () => {
    let s = seeded()
    s = exploreReducer(s, { type: 'toggleSort', columnId: 'a' })
    s = exploreReducer(s, { type: 'setFilter', columnId: 'a', state: { operator: 'contains', value: 'foo' } })
    s = exploreReducer(s, { type: 'setFilter', columnId: 'b', state: { selected: ['x', 'y'] } })
    const restored = stateFromSpec(specFromState(s))
    expect(restored.graphUris).toEqual(s.graphUris)
    expect(restored.classUris).toEqual(s.classUris)
    expect(restored.columns.map((c) => c.id)).toEqual(['a', 'b', 'c'])
    expect(restored.sort).toEqual([{ column_id: 'a', direction: 'asc' }])
    expect(restored.filters.a).toEqual({ operator: 'contains', value: 'foo' })
    expect(restored.filters.b).toEqual({ selected: ['x', 'y'] })
  })
})
