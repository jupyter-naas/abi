import { describe, expect, it } from 'vitest'
import {
  appendStep,
  buildFullQuery,
  generateSparql,
  MANUAL_INSTANCE_SELECT_ID,
  removeStepsByType,
  upsertStep,
  upsertStepById,
  type SparqlStep,
} from './sparql-steps'

// ── helpers ───────────────────────────────────────────────────────────────────

const G = 'http://example.org/graph'

function makeStep(overrides: Partial<SparqlStep>): SparqlStep {
  return {
    id: 'test',
    type: 'search',
    label: 'test',
    sparql: '',
    params: { type: 'search', search: 'foo', graphUri: G },
    timestamp: 0,
    ...overrides,
  }
}

// ── generateSparql ────────────────────────────────────────────────────────────

describe('generateSparql', () => {
  it('search — escapes quotes and lowercases', () => {
    const q = generateSparql({ type: 'search', search: 'Foo "bar"', graphUri: G })
    expect(q).toContain('foo \\"bar\\"')
    expect(q).toContain(`GRAPH <${G}>`)
  })

  it('class_filter — emits VALUES block', () => {
    const q = generateSparql({
      type: 'class_filter',
      classUris: ['http://ex.org/Agent'],
      classLabels: ['Agent'],
      graphUri: G,
    })
    expect(q).toContain('<http://ex.org/Agent>')
    expect(q).toContain('VALUES ?class')
  })

  it('property_filter — emits VALUES for prop', () => {
    const q = generateSparql({
      type: 'property_filter',
      propertyUris: ['http://ex.org/name'],
      graphUri: G,
    })
    expect(q).toContain('<http://ex.org/name>')
    expect(q).toContain('VALUES ?prop')
  })

  it('instance_select — emits VALUES for ind', () => {
    const q = generateSparql({
      type: 'instance_select',
      instanceUris: ['http://ex.org/alice', 'http://ex.org/bob'],
      graphUri: G,
    })
    expect(q).toContain('<http://ex.org/alice>')
    expect(q).toContain('VALUES ?ind')
  })

  it('relation_select — no FILTER when excludedInstanceUris is empty', () => {
    const q = generateSparql({
      type: 'relation_select',
      relationUris: ['http://ex.org/knows'],
      selectedRowKeys: [],
      excludedInstanceUris: [],
      graphUri: G,
    })
    expect(q).not.toContain('FILTER')
    expect(q).toContain('VALUES ?p')
  })

  it('relation_select — NOT IN filter when exclusions exist', () => {
    const q = generateSparql({
      type: 'relation_select',
      relationUris: ['http://ex.org/knows'],
      selectedRowKeys: [],
      excludedInstanceUris: ['http://ex.org/charlie'],
      graphUri: G,
    })
    expect(q).toContain('NOT IN')
    expect(q).toContain('<http://ex.org/charlie>')
  })

  it('exclusion — emits FILTER NOT IN for individuals', () => {
    const q = generateSparql({
      type: 'exclusion',
      excludedInstanceUris: ['http://ex.org/alice'],
      excludedRelationRowKeys: [],
    })
    expect(q).toContain('NOT IN')
    expect(q).toContain('<http://ex.org/alice>')
  })

  it('default_properties — mentions rdfs:label and rdf:type', () => {
    const q = generateSparql({ type: 'default_properties', graphUri: G })
    expect(q).toContain('rdf-syntax-ns#type')
    expect(q).toContain('rdf-schema#label')
  })

  it('property_projection — scopes to class and lists properties', () => {
    const q = generateSparql({
      type: 'property_projection',
      classUri: 'http://ex.org/Agent',
      classLabel: 'Agent',
      propertyUris: ['http://ex.org/system_prompt'],
      graphUri: G,
    })
    expect(q).toContain('?ind a <http://ex.org/Agent>')
    expect(q).toContain('<http://ex.org/system_prompt>')
  })
})

// ── buildFullQuery ────────────────────────────────────────────────────────────

describe('buildFullQuery', () => {
  it('returns placeholder when steps is empty', () => {
    const q = buildFullQuery([], G)
    expect(q).toContain('#')
    expect(q).not.toContain('CONSTRUCT {')
  })

  it('returns placeholder when graphUri is empty', () => {
    const steps = [makeStep({})]
    const q = buildFullQuery(steps, '')
    expect(q).not.toContain('CONSTRUCT {')
  })

  it('basic CONSTRUCT with single instance_select step', () => {
    const params = { type: 'instance_select' as const, instanceUris: ['http://ex.org/alice'], graphUri: G }
    const step = makeStep({ type: 'instance_select', params })
    const q = buildFullQuery([step], G)
    expect(q).toContain('CONSTRUCT')
    expect(q).toContain('VALUES ?ind')
    expect(q).toContain('<http://ex.org/alice>')
    expect(q).not.toContain('UNION')
  })

  it('merges URIs from multiple instance_select steps', () => {
    const step1 = makeStep({
      id: MANUAL_INSTANCE_SELECT_ID,
      type: 'instance_select',
      params: { type: 'instance_select', instanceUris: ['http://ex.org/alice'], graphUri: G },
    })
    const step2 = makeStep({
      id: 'rel_step',
      type: 'instance_select',
      params: { type: 'instance_select', instanceUris: ['http://ex.org/bob'], graphUri: G },
    })
    const q = buildFullQuery([step1, step2], G)
    expect(q).toContain('<http://ex.org/alice>')
    expect(q).toContain('<http://ex.org/bob>')
  })

  it('relation step with no exclusions — no FILTER in UNION', () => {
    const instStep = makeStep({
      type: 'instance_select',
      params: { type: 'instance_select', instanceUris: ['http://ex.org/alice'], graphUri: G },
    })
    const relStep = makeStep({
      type: 'relation_select',
      params: {
        type: 'relation_select',
        relationUris: ['http://ex.org/knows'],
        selectedRowKeys: [],
        excludedInstanceUris: [],
        graphUri: G,
      },
    })
    const q = buildFullQuery([instStep, relStep], G)
    expect(q).toContain('UNION')
    expect(q).not.toMatch(/FILTER\(\?s NOT IN/)
  })

  it('relation step with exclusions — NOT IN in UNION', () => {
    const instStep = makeStep({
      type: 'instance_select',
      params: { type: 'instance_select', instanceUris: ['http://ex.org/alice'], graphUri: G },
    })
    const relStep = makeStep({
      type: 'relation_select',
      params: {
        type: 'relation_select',
        relationUris: ['http://ex.org/knows'],
        selectedRowKeys: [],
        excludedInstanceUris: ['http://ex.org/charlie'],
        graphUri: G,
      },
    })
    const q = buildFullQuery([instStep, relStep], G)
    expect(q).toContain('NOT IN')
    expect(q).toContain('<http://ex.org/charlie>')
  })

  it('exclusion step applies FILTER to individuals subquery', () => {
    const instStep = makeStep({
      type: 'instance_select',
      params: { type: 'instance_select', instanceUris: ['http://ex.org/alice', 'http://ex.org/bob'], graphUri: G },
    })
    const excStep = makeStep({
      type: 'exclusion',
      params: { type: 'exclusion', excludedInstanceUris: ['http://ex.org/bob'], excludedRelationRowKeys: [] },
    })
    const q = buildFullQuery([instStep, excStep], G)
    expect(q).toContain('FILTER(?ind NOT IN')
    expect(q).toContain('<http://ex.org/bob>')
  })

  it('default_properties adds OPTIONAL block with pp_0 variable', () => {
    const instStep = makeStep({
      type: 'instance_select',
      params: { type: 'instance_select', instanceUris: ['http://ex.org/alice'], graphUri: G },
    })
    const dpStep = makeStep({
      type: 'default_properties',
      params: { type: 'default_properties', graphUri: G },
    })
    const q = buildFullQuery([instStep, dpStep], G)
    expect(q).toContain('OPTIONAL')
    expect(q).toContain('?pp_0')
    expect(q).toContain('?pv_0')
    expect(q).toContain('rdf-schema#label')
  })

  it('property_projection adds OPTIONAL scoped to class', () => {
    const instStep = makeStep({
      type: 'instance_select',
      params: { type: 'instance_select', instanceUris: ['http://ex.org/alice'], graphUri: G },
    })
    const projStep = makeStep({
      type: 'property_projection',
      params: {
        type: 'property_projection',
        classUri: 'http://ex.org/Agent',
        classLabel: 'Agent',
        propertyUris: ['http://ex.org/system_prompt'],
        graphUri: G,
      },
    })
    const q = buildFullQuery([instStep, projStep], G)
    expect(q).toContain('?ind a <http://ex.org/Agent>')
    expect(q).toContain('?pp_1')
    expect(q).toContain('<http://ex.org/system_prompt>')
  })
})

// ── step management ───────────────────────────────────────────────────────────

describe('upsertStep', () => {
  it('appends when no matching type exists', () => {
    const result = upsertStep([], makeStep({ type: 'search' }))
    expect(result).toHaveLength(1)
    expect(result[0].type).toBe('search')
  })

  it('replaces the first step of the same type', () => {
    const existing = [makeStep({ id: 'a', type: 'search', label: 'old' })]
    const { id: _id, timestamp: _ts, ...step } = makeStep({ type: 'search', label: 'new' })
    const result = upsertStep(existing, step)
    expect(result).toHaveLength(1)
    expect(result[0].label).toBe('new')
  })
})

describe('upsertStepById', () => {
  it('replaces step with matching id', () => {
    const existing = [makeStep({ id: 'my-id', label: 'old' })]
    const { id: _id, timestamp: _ts, ...step } = makeStep({ label: 'new' })
    const result = upsertStepById(existing, 'my-id', step)
    expect(result).toHaveLength(1)
    expect(result[0].label).toBe('new')
    expect(result[0].id).toBe('my-id')
  })

  it('appends when id not found', () => {
    const result = upsertStepById([], 'my-id', makeStep({ label: 'new' }))
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe('my-id')
  })

  it('does not replace different-type step with same-type scan (unlike upsertStep)', () => {
    const rel = makeStep({ id: 'rel-id', type: 'instance_select', label: 'rel' })
    const manual = makeStep({ id: MANUAL_INSTANCE_SELECT_ID, type: 'instance_select', label: 'manual' })
    const existing = [rel, manual]
    // upsertStepById with rel-id should only replace rel, not manual
    const { id: _id, timestamp: _ts, ...relUpdated } = makeStep({ type: 'instance_select', label: 'rel-updated' })
    const result = upsertStepById(existing, 'rel-id', relUpdated)
    expect(result).toHaveLength(2)
    expect(result[0].label).toBe('rel-updated')
    expect(result[1].label).toBe('manual')
  })
})

describe('appendStep', () => {
  it('always appends regardless of existing types', () => {
    const existing = [makeStep({ type: 'exclusion' })]
    const result = appendStep(existing, makeStep({ type: 'exclusion' }))
    expect(result).toHaveLength(2)
  })
})

describe('removeStepsByType', () => {
  it('removes all steps of the given type', () => {
    const steps = [
      makeStep({ id: '1', type: 'search' }),
      makeStep({ id: '2', type: 'class_filter' }),
      makeStep({ id: '3', type: 'search' }),
    ]
    const result = removeStepsByType(steps, 'search')
    expect(result).toHaveLength(1)
    expect(result[0].type).toBe('class_filter')
  })
})
