import { describe, expect, it } from 'vitest'
import { flipHop, inversePathToAncestor, rebaseColumn, rootNode, upstreamConditions, type SpineNode } from './pipeline'
import type { Column } from './types'

const D = 'http://x#'
const propCol = (id: string, pred: string): Column => ({
  id,
  datatype: 'string',
  source: { kind: 'property', predicate: pred, path: [] },
})

/** paper -has_chunks-> chunk -has_extracted_item-> item, grain = item. */
function spine(paperFilters: Record<string, { operator?: 'contains'; value?: string }> = {}): SpineNode[] {
  return [
    { ...rootNode(D + 'PDFPaperFile', 'PDFPaperFile'), filters: paperFilters as never, columns: [propCol('path', D + 'path')] },
    { ...rootNode(D + 'Chunk', 'Chunk'), via: { predicate: D + 'has_chunks', direction: 'out' } },
    { ...rootNode(D + 'ExtractedItem', 'ExtractedItem'), via: { predicate: D + 'has_extracted_item', direction: 'out' } },
  ]
}

describe('inversePathToAncestor', () => {
  it('reverses and flips the hops from grain back to the ancestor', () => {
    expect(inversePathToAncestor(spine(), 0)).toEqual([
      { predicate: D + 'has_extracted_item', direction: 'in', quantifier: 'one' },
      { predicate: D + 'has_chunks', direction: 'in', quantifier: 'one' },
    ])
  })
  it('is empty for the grain itself', () => {
    expect(inversePathToAncestor(spine(), 2)).toEqual([])
  })
  it('returns one hop to the immediate parent', () => {
    expect(inversePathToAncestor(spine(), 1)).toEqual([
      { predicate: D + 'has_extracted_item', direction: 'in', quantifier: 'one' },
    ])
  })
})

describe('flipHop / rebaseColumn', () => {
  it('flips the direction into a single inverse hop', () => {
    expect(flipHop({ predicate: D + 'has_chunks', direction: 'out' })).toEqual({
      predicate: D + 'has_chunks',
      direction: 'in',
      quantifier: 'one',
    })
  })
  it('prefixes an own-column path with the inverse hop and labels it with the source class', () => {
    const hop = flipHop({ predicate: D + 'has_chunks', direction: 'out' })
    const col = rebaseColumn(propCol('path', D + 'path'), hop, 'PDFPaperFile')
    expect(col.id).toBe('path')
    expect(col.label).toBe('PDFPaperFile · path')
    expect(col.source).toEqual({
      kind: 'property',
      predicate: D + 'path',
      path: [{ predicate: D + 'has_chunks', direction: 'in', quantifier: 'one' }],
    })
  })
  it('extends an already-traversed column without re-labelling it', () => {
    const hop = flipHop({ predicate: D + 'has_extracted_item', direction: 'out' })
    const carried: Column = {
      id: 'path',
      datatype: 'string',
      label: 'PDFPaperFile · path',
      source: { kind: 'property', predicate: D + 'path', path: [{ predicate: D + 'has_chunks', direction: 'in', quantifier: 'one' }] },
    }
    const col = rebaseColumn(carried, hop, 'Chunk')
    expect(col.label).toBe('PDFPaperFile · path') // not re-prefixed
    expect((col.source as { path: unknown[] }).path).toHaveLength(2)
  })
})

describe('upstreamConditions', () => {
  it('is empty when no ancestor has filters', () => {
    expect(upstreamConditions(spine())).toEqual([])
  })
  it("compiles an ancestor's filter to a source condition via the inverse path", () => {
    const conds = upstreamConditions(spine({ path: { operator: 'contains', value: 'pubmed' } }))
    expect(conds).toEqual([
      {
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
      },
    ])
  })
})
