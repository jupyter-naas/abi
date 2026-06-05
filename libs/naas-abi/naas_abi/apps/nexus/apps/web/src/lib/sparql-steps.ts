// SPARQL step tracking — represents each user action in the graph discovery
// UI as an executable SPARQL query, mirroring the PowerQuery model.

export type StepType =
  | 'search'
  | 'class_filter'
  | 'property_filter'
  | 'instance_select'
  | 'relation_select'
  | 'exclusion'
  | 'default_properties'
  | 'property_projection'

// ── Param shapes (one per step type) ─────────────────────────────────────────

export interface SearchParams {
  type: 'search'
  search: string
  graphUri: string
}

export interface ClassFilterParams {
  type: 'class_filter'
  classUris: string[]
  classLabels: string[]
  graphUri: string
}

export interface PropertyFilterParams {
  type: 'property_filter'
  propertyUris: string[]
  graphUri: string
}

export interface InstanceSelectParams {
  type: 'instance_select'
  instanceUris: string[]
  graphUri: string
}

export interface RelationSelectParams {
  type: 'relation_select'
  relationUris: string[]
  selectedRowKeys: string[]
  // URIs to exclude from the triple pattern; empty = no FILTER (all selected).
  excludedInstanceUris: string[]
  graphUri: string
}

export interface ExclusionParams {
  type: 'exclusion'
  excludedInstanceUris: string[]
  excludedRelationRowKeys: string[]
}

export interface DefaultPropertiesParams {
  type: 'default_properties'
  graphUri: string
}

export interface PropertyProjectionParams {
  type: 'property_projection'
  classUri: string
  classLabel: string
  propertyUris: string[]
  graphUri: string
}

export type StepParams =
  | SearchParams
  | ClassFilterParams
  | PropertyFilterParams
  | InstanceSelectParams
  | RelationSelectParams
  | ExclusionParams
  | DefaultPropertiesParams
  | PropertyProjectionParams

export interface SparqlStep {
  id: string
  type: StepType
  label: string
  sparql: string
  params: StepParams
  timestamp: number
}

// ── SPARQL generators ─────────────────────────────────────────────────────────

function uriList(uris: string[], pad = '      '): string {
  return uris.map((u) => `${pad}<${u}>`).join('\n')
}

function generateSearchSparql(p: SearchParams): string {
  const escaped = p.search.toLowerCase().replace(/\\/g, '\\\\').replace(/"/g, '\\"')
  return `SELECT DISTINCT ?ind WHERE {
  GRAPH <${p.graphUri}> {
    ?ind a ?class .
    ?ind ?prop ?val .
    FILTER(CONTAINS(LCASE(STR(?val)), "${escaped}"))
  }
}`
}

function generateClassFilterSparql(p: ClassFilterParams): string {
  return `SELECT DISTINCT ?ind WHERE {
  GRAPH <${p.graphUri}> {
    ?ind a ?class .
    VALUES ?class {
${uriList(p.classUris)}
    }
  }
}`
}

function generatePropertyFilterSparql(p: PropertyFilterParams): string {
  return `SELECT DISTINCT ?ind ?prop ?val WHERE {
  GRAPH <${p.graphUri}> {
    ?ind a ?class .
    ?ind ?prop ?val .
    VALUES ?prop {
${uriList(p.propertyUris)}
    }
  }
}`
}

function generateInstanceSelectSparql(p: InstanceSelectParams): string {
  return `# All data properties for selected individuals
SELECT DISTINCT ?ind ?prop ?val WHERE {
  GRAPH <${p.graphUri}> {
    ?ind a ?class .
    ?ind ?prop ?val .
    VALUES ?ind {
${uriList(p.instanceUris)}
    }
  }
}`
}

function generateRelationSelectSparql(p: RelationSelectParams): string {
  const lines = [
    `SELECT DISTINCT ?s ?p ?o WHERE {`,
    `  GRAPH <${p.graphUri}> {`,
    `    ?s ?p ?o .`,
    `    VALUES ?p {`,
    ...p.relationUris.map((u) => `      <${u}>`),
    `    }`,
  ]
  if (p.excludedInstanceUris.length > 0) {
    const excList = p.excludedInstanceUris.map((u) => `<${u}>`).join(' ')
    lines.push(`    FILTER(?s NOT IN (${excList}) && ?o NOT IN (${excList}))`)
  }
  lines.push(`  }`)
  lines.push(`}`)
  return lines.join('\n')
}

function generateExclusionSparql(p: ExclusionParams): string {
  const parts: string[] = []
  if (p.excludedInstanceUris.length > 0) {
    const inList = p.excludedInstanceUris.map((u) => `<${u}>`).join(' ')
    parts.push(
      `# Removing ${p.excludedInstanceUris.length} individual(s) from working set\nFILTER(?ind NOT IN (${inList}))`
    )
  }
  if (p.excludedRelationRowKeys.length > 0) {
    parts.push(
      `# Removing ${p.excludedRelationRowKeys.length} relation row(s)\n# Row keys:\n${p.excludedRelationRowKeys.map((k) => `# - ${k}`).join('\n')}`
    )
  }
  return parts.join('\n\n') || '# No exclusions'
}

function generateDefaultPropertiesSparql(p: DefaultPropertiesParams): string {
  return `# Default properties for all individuals
SELECT DISTINCT ?ind ?prop ?val WHERE {
  GRAPH <${p.graphUri}> {
    ?ind a ?class .
    ?ind ?prop ?val .
    VALUES ?prop {
      <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>
      <http://www.w3.org/2000/01/rdf-schema#label>
    }
  }
}`
}

function generatePropertyProjectionSparql(p: PropertyProjectionParams): string {
  return `# ${p.classLabel} — ${p.propertyUris.length} propert${p.propertyUris.length > 1 ? 'ies' : 'y'}
SELECT DISTINCT ?ind ?prop ?val WHERE {
  GRAPH <${p.graphUri}> {
    ?ind a <${p.classUri}> .
    ?ind ?prop ?val .
    VALUES ?prop {
${uriList(p.propertyUris)}
    }
  }
}`
}

export function generateSparql(params: StepParams): string {
  switch (params.type) {
    case 'search':
      return generateSearchSparql(params)
    case 'class_filter':
      return generateClassFilterSparql(params)
    case 'property_filter':
      return generatePropertyFilterSparql(params)
    case 'instance_select':
      return generateInstanceSelectSparql(params)
    case 'relation_select':
      return generateRelationSelectSparql(params)
    case 'exclusion':
      return generateExclusionSparql(params)
    case 'default_properties':
      return generateDefaultPropertiesSparql(params)
    case 'property_projection':
      return generatePropertyProjectionSparql(params)
  }
}

// ── Final combined query ──────────────────────────────────────────────────────

export function buildFullQuery(steps: SparqlStep[], graphUri: string): string {
  if (!graphUri || steps.length === 0) {
    return [
      '# Full CONSTRUCT query will appear here once you add steps.',
      '# Steps: Search → Class filter → Instance select → Relation select',
    ].join('\n')
  }

  const searchStep = steps.find((s) => s.type === 'search')
  const classStep  = steps.find((s) => s.type === 'class_filter')
  const propStep   = steps.find((s) => s.type === 'property_filter')
  // Merge all instance_select steps (manual + relation-derived) into one VALUES block.
  const allInstUris = [
    ...new Set(
      steps
        .filter((s) => s.type === 'instance_select')
        .flatMap((s) => (s.params as InstanceSelectParams).instanceUris)
    ),
  ]
  const relStep    = steps.find((s) => s.type === 'relation_select')
  const excSteps   = steps.filter((s) => s.type === 'exclusion').map((s) => s.params as ExclusionParams)
  const excludedUris = [...new Set(excSteps.flatMap((e) => e.excludedInstanceUris))]

  const defaultPropsStep  = steps.find((s) => s.type === 'default_properties')
  const projSteps = steps
    .filter((s) => s.type === 'property_projection')
    .map((s) => s.params as PropertyProjectionParams)

  // Index-based unique variable names for each OPTIONAL projection block.
  interface ProjVar { pp: string; pv: string }
  const projVars: ProjVar[] = []
  if (defaultPropsStep) projVars.push({ pp: '?pp_0', pv: '?pv_0' })
  for (let i = 0; i < projSteps.length; i++) {
    projVars.push({ pp: `?pp_${i + 1}`, pv: `?pv_${i + 1}` })
  }

  const hasRelations   = relStep !== undefined
  const hasProjections = projVars.length > 0

  const out: string[] = [
    `# Full query — composed from ${steps.length} step(s)`,
    ...steps.map((s, i) => `# Step ${i + 1}: ${s.label}`),
    '',
    'CONSTRUCT {',
    '  ?ind ?prop ?val .',
    ...projVars.map((v) => `  ?ind ${v.pp} ${v.pv} .`),
    ...(hasRelations ? ['  ?s ?rp ?o .'] : []),
    '}',
    'WHERE {',
    '  {',
    '    # Filtered individuals',
    '    {',
    '      SELECT DISTINCT ?ind WHERE {',
    `        GRAPH <${graphUri}> {`,
    '          ?ind a ?class .',
  ]

  if (searchStep) {
    const sp = searchStep.params as SearchParams
    const esc = sp.search.toLowerCase().replace(/\\/g, '\\\\').replace(/"/g, '\\"')
    out.push('          ?ind ?_sp ?_sv .')
    out.push(`          FILTER(CONTAINS(LCASE(STR(?_sv)), "${esc}"))`)
  }
  if (classStep) {
    const cp = classStep.params as ClassFilterParams
    out.push('          VALUES ?class {')
    for (const u of cp.classUris) out.push(`            <${u}>`)
    out.push('          }')
  }
  if (propStep) {
    const pp = propStep.params as PropertyFilterParams
    out.push('          ?ind ?_pfp ?_pfv .')
    out.push('          VALUES ?_pfp {')
    for (const u of pp.propertyUris) out.push(`            <${u}>`)
    out.push('          }')
  }
  if (allInstUris.length > 0) {
    out.push('          VALUES ?ind {')
    for (const u of allInstUris) out.push(`            <${u}>`)
    out.push('          }')
  }
  if (excludedUris.length > 0) {
    out.push(`          FILTER(?ind NOT IN (${excludedUris.map((u) => `<${u}>`).join(' ')}))`)
  }

  out.push(
    '        }',
    '      }',
    '    }',
    `    GRAPH <${graphUri}> {`,
    '      ?ind ?prop ?val .',
    '    }',
  )

  // OPTIONAL projection blocks (default properties + class-specific).
  if (hasProjections) {
    let vi = 0
    if (defaultPropsStep) {
      const { pp, pv } = projVars[vi++]
      out.push(
        `    # Default properties`,
        `    OPTIONAL {`,
        `      GRAPH <${graphUri}> {`,
        `        ?ind ${pp} ${pv} .`,
        `        VALUES ${pp} {`,
        `          <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>`,
        `          <http://www.w3.org/2000/01/rdf-schema#label>`,
        `        }`,
        `      }`,
        `    }`,
      )
    }
    for (const pp_step of projSteps) {
      const { pp, pv } = projVars[vi++]
      out.push(
        `    # ${pp_step.classLabel}`,
        `    OPTIONAL {`,
        `      GRAPH <${graphUri}> {`,
        `        ?ind a <${pp_step.classUri}> .`,
        `        ?ind ${pp} ${pv} .`,
        `        VALUES ${pp} {`,
        ...pp_step.propertyUris.map((u) => `          <${u}>`),
        `        }`,
        `      }`,
        `    }`,
      )
    }
  }

  out.push('  }')

  if (relStep) {
    const rp = relStep.params as RelationSelectParams
    // Merge relation-level exclusions with individual-level exclusions.
    const allRelExcluded = [...new Set([...rp.excludedInstanceUris, ...excludedUris])]
    out.push('  UNION')
    out.push('  {')
    out.push(`    GRAPH <${graphUri}> {`)
    out.push('      ?s ?rp ?o .')
    out.push('      VALUES ?rp {')
    for (const u of rp.relationUris) out.push(`        <${u}>`)
    out.push('      }')
    if (allRelExcluded.length > 0) {
      const excList = allRelExcluded.map((u) => `<${u}>`).join(' ')
      out.push(`      FILTER(?s NOT IN (${excList}) && ?o NOT IN (${excList}))`)
    }
    out.push('    }')
    out.push('  }')
  }

  out.push('}')
  return out.join('\n')
}

// ── Step management ───────────────────────────────────────────────────────────

let _counter = 0
function nextId(): string {
  return `step_${(++_counter).toString()}_${Date.now().toString(36)}`
}

export const MANUAL_INSTANCE_SELECT_ID = 'instance_select_manual'

/** Replace existing step of the same type, or append if none exists. */
export function upsertStep(
  steps: SparqlStep[],
  step: Omit<SparqlStep, 'id' | 'timestamp'>
): SparqlStep[] {
  const idx = steps.findIndex((s) => s.type === step.type)
  const next: SparqlStep = { ...step, id: nextId(), timestamp: Date.now() }
  if (idx >= 0) {
    const out = [...steps]
    out[idx] = next
    return out
  }
  return [...steps, next]
}

/**
 * Replace the step with the given stable id, or append if not found.
 * Use when multiple steps of the same type coexist (e.g. manual vs
 * relation-derived instance_select).
 */
export function upsertStepById(
  steps: SparqlStep[],
  id: string,
  step: Omit<SparqlStep, 'id' | 'timestamp'>
): SparqlStep[] {
  const idx = steps.findIndex((s) => s.id === id)
  const next: SparqlStep = { ...step, id, timestamp: Date.now() }
  if (idx >= 0) {
    const out = [...steps]
    out[idx] = next
    return out
  }
  return [...steps, next]
}

/** Always append — used for exclusion steps which stack up over time. */
export function appendStep(
  steps: SparqlStep[],
  step: Omit<SparqlStep, 'id' | 'timestamp'>
): SparqlStep[] {
  return [...steps, { ...step, id: nextId(), timestamp: Date.now() }]
}

export function removeStepsByType(steps: SparqlStep[], type: StepType): SparqlStep[] {
  return steps.filter((s) => s.type !== type)
}
