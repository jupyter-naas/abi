import React, { useEffect, useRef } from 'react';

const C = {
  external:       { bg: '#f8fafc', border: '#94a3b8' },
  interface:      { bg: '#d1fae5', border: '#22c55e' },
  application:    { bg: '#dbeafe', border: '#3b82f6' },
  intelligence:   { bg: '#fef9c3', border: '#eab308' },
  services:       { bg: '#ede9fe', border: '#8b5cf6' },
  infrastructure: { bg: '#fce7f3', border: '#ec4899' },
};

const LEGEND = [
  { key: 'interface',       label: '① Interface' },
  { key: 'application',    label: '② Application' },
  { key: 'intelligence',   label: '③ Intelligence' },
  { key: 'services',       label: '④ Services' },
  { key: 'infrastructure', label: '⑤ Infrastructure' },
  { key: 'external',       label: 'External' },
];

// Locked positions (user-defined)
const POS = {
  'users':          { x:   -7, y: -382 },
  'nexus-web':      { x: -522, y: -277 },
  'cli':            { x: -225, y: -270 },
  'mcp-clients':    { x:   34, y: -275 },
  'sparql-wb':      { x:  309, y: -272 },
  'dagster-ui':     { x:  561, y: -277 },
  'abi-api':        { x: -279, y: -168 },
  'nexus-api':      { x: -522, y: -173 },
  'mcp-server':     { x:   45, y: -168 },
  'dagster':        { x:  567, y: -165 },
  'engine':         { x:  -23, y:  -33 },
  'modules':        { x:  473, y:  -42 },
  'abiagent':       { x:  -55, y:   58 },
  'agents':         { x:  243, y:   44 },
  'marketplace':    { x: -279, y:  -44 },
  'openrouter':     { x: -523, y:  -47 },
  'ollama':         { x: -509, y:   36 },
  'triple-store':   { x: -531, y:  163 },
  'vector-store':   { x: -311, y:  163 },
  'object-storage': { x: -102, y:  165 },
  'message-bus':    { x:  141, y:  167 },
  'kv-cache':       { x:  350, y:  165 },
  'secret':         { x:  561, y:  165 },
  'fuseki':         { x: -533, y:  275 },
  'qdrant':         { x: -332, y:  273 },
  'postgres':       { x: -148, y:  273 },
  'minio':          { x:   40, y:  275 },
  'rabbitmq':       { x:  226, y:  275 },
  'redis':          { x:  409, y:  273 },
  'caddy':          { x:  595, y:  275 },
  'llm-ext':        { x: -135, y:  399 },
  'api-ext':        { x:   87, y:  401 },
};

// NODE_LAYER: id → { group, level } — used for band computation only
const NODE_LAYER = {};

function node(id, label, group, level) {
  NODE_LAYER[id] = { group, level };
  const { bg, border } = C[group];
  const { x, y } = POS[id];
  return {
    id, label, x, y,
    // 'group' omitted — vis.js would override explicit colors with its default palette
    shape: 'box',
    margin: { top: 8, bottom: 8, left: 10, right: 10 },
    font: { size: 12, color: '#1e293b', face: 'ui-sans-serif, system-ui, sans-serif', multi: false },
    color: { background: bg, border, highlight: { background: bg, border }, hover: { background: bg, border } },
    borderWidth: 2,
    borderWidthSelected: 3,
    shadow: { enabled: true, color: 'rgba(0,0,0,0.07)', size: 6, x: 0, y: 2 },
    widthConstraint: { minimum: 150, maximum: 220 },
  };
}

function edge(from, to, opts = {}) {
  return { from, to, ...opts };
}

const NODES = [
  node('users',          'Users & AI Clients',                                                                    'external',       0),
  node('nexus-web',      'Nexus Web  :3042\nNext.js',                                                            'interface',      1),
  node('cli',            'abi CLI\nstack · chat · new · deploy · run',                                           'interface',      1),
  node('mcp-clients',    'MCP Clients\nClaude Desktop · Cursor · VS Code',                                       'interface',      1),
  node('sparql-wb',      'SPARQL Workbench  :3000',                                                              'interface',      1),
  node('dagster-ui',     'Dagster UI  :3001',                                                                    'interface',      1),
  node('abi-api',        'ABI Core API  :9879\nFastAPI  /agents · /workflows · /graph',                         'application',    2),
  node('nexus-api',      'Nexus API  /api\nFastAPI  auth · chat · workspaces · files',                          'application',    2),
  node('mcp-server',     'MCP Server  :8000\nHTTP  or  STDIO',                                                  'application',    2),
  node('dagster',        'Dagster\nSchedules · Sensors · Assets',                                               'application',    2),
  node('engine',         'Engine  naas-abi-core\nload() · service wiring · ontology loading',                   'intelligence',   3),
  node('modules',        'Module System\ncore · marketplace · custom\nonto2py · TemplatableSparqlQuery',        'intelligence',   3),
  node('abiagent',       'AbiAgent\nsupervisor · intent routing',                                               'intelligence',   4),
  node('agents',         'Built-in Agents\nOntologyEngineer · KnowledgeGraph\nEntityToSPARQL · Coding',         'intelligence',   4),
  node('marketplace',    'Marketplace Agents\n100+ domain agents',                                              'intelligence',   4),
  node('openrouter',     'OpenRouter\nGPT · Claude · Gemini\nMistral · Qwen · DeepSeek',                       'intelligence',   4),
  node('ollama',         'Ollama  (local / air-gapped)\nQwen3 · DeepSeek-R1 · Gemma3',                         'intelligence',   4),
  node('triple-store',   'Triple Store\nFuseki TDB2 · Oxigraph · Neptune · FS',                                'services',       5),
  node('vector-store',   'Vector Store\nQdrant · in-memory',                                                    'services',       5),
  node('object-storage', 'Object Storage\nMinIO / S3 · FS · Naas',                                             'services',       5),
  node('message-bus',    'Message Bus\nRabbitMQ · Python queue',                                               'services',       5),
  node('kv-cache',       'KV + Cache\nRedis · Python / FS',                                                    'services',       5),
  node('secret',         'Secret\ndotenv · Naas · Base64',                                                     'services',       5),
  node('fuseki',         'Fuseki  :3030',                                                                       'infrastructure', 6),
  node('qdrant',         'Qdrant  :6333',                                                                       'infrastructure', 6),
  node('postgres',       'PostgreSQL  :5432',                                                                   'infrastructure', 6),
  node('minio',          'MinIO  :9000',                                                                        'infrastructure', 6),
  node('rabbitmq',       'RabbitMQ  :5672',                                                                     'infrastructure', 6),
  node('redis',          'Redis  :6379',                                                                        'infrastructure', 6),
  node('caddy',          'Caddy  :80/:443',                                                                     'infrastructure', 6),
  node('llm-ext',        'LLM Providers\nOpenAI · Anthropic · Google\nMistral · Meta',                         'external',       7),
  node('api-ext',        'External APIs\nGitHub · LinkedIn · Salesforce\nGmail · Stripe · ...',                'external',       7),
];

const EDGES = [
  edge('users', 'nexus-web'), edge('users', 'cli'), edge('users', 'mcp-clients'),
  edge('users', 'sparql-wb'), edge('users', 'dagster-ui'),
  edge('nexus-web', 'nexus-api'), edge('nexus-web', 'abi-api'),
  edge('cli', 'abi-api'), edge('cli', 'mcp-server'),
  edge('mcp-clients', 'mcp-server'), edge('dagster-ui', 'dagster'),
  edge('abi-api', 'engine'), edge('nexus-api', 'engine'),
  edge('mcp-server', 'engine'), edge('dagster', 'engine'),
  edge('engine', 'abiagent'), edge('engine', 'agents'),
  edge('engine', 'marketplace'), edge('engine', 'modules'),
  edge('abiagent', 'openrouter'), edge('abiagent', 'ollama'),
  edge('agents', 'openrouter'), edge('marketplace', 'openrouter'),
  edge('engine', 'triple-store'), edge('engine', 'vector-store'),
  edge('engine', 'object-storage'), edge('engine', 'message-bus'),
  edge('engine', 'kv-cache'), edge('engine', 'secret'),
  edge('triple-store', 'fuseki'), edge('vector-store', 'qdrant'),
  edge('object-storage', 'minio'), edge('message-bus', 'rabbitmq'),
  edge('kv-cache', 'redis'),
  edge('nexus-api', 'postgres'),
  edge('sparql-wb', 'fuseki', { dashes: true }),
  edge('openrouter', 'llm-ext'), edge('modules', 'api-ext'),
];

// Layer bands: compute geometry once from the locked POS coordinates
const PAD_X = 140;
const PAD_Y = 46;
const LAYER_BANDS = (() => {
  const defs = [
    { label: '① Interface',       levels: [1],    group: 'interface' },
    { label: '② Application',     levels: [2],    group: 'application' },
    { label: '③ Intelligence',    levels: [3, 4], group: 'intelligence' },
    { label: '④ Services',        levels: [5],    group: 'services' },
    { label: '⑤ Infrastructure',  levels: [6],    group: 'infrastructure' },
  ];
  const allX = Object.values(POS).map(p => p.x);
  const bandMinX = Math.min(...allX) - PAD_X;
  const bandMaxX = Math.max(...allX) + PAD_X;
  return defs.map(({ label, levels, group }) => {
    const ys = Object.entries(NODE_LAYER)
      .filter(([, v]) => levels.includes(v.level))
      .map(([id]) => POS[id]?.y)
      .filter(y => y != null);
    return { label, group, bandMinX, bandMaxX, minY: Math.min(...ys) - PAD_Y, maxY: Math.max(...ys) + PAD_Y };
  });
})();

function drawRoundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

const OPTIONS = {
  layout: { randomSeed: 0 },
  physics: { enabled: false },
  interaction: { hover: true, zoomView: false, dragView: false, dragNodes: false, tooltipDelay: 150 },
  edges: {
    arrows: { to: { enabled: true, scaleFactor: 0.55 } },
    color: { color: '#cbd5e1', highlight: '#64748b', hover: '#94a3b8', opacity: 0.85 },
    width: 1.5,
    smooth: { enabled: true, type: 'cubicBezier', forceDirection: 'vertical', roundness: 0.35 },
  },
  nodes: { widthConstraint: { maximum: 220 } },
};

export default function ArchitectureGraph() {
  const containerRef = useRef(null);

  useEffect(() => {
    let network;
    (async () => {
      const { Network, DataSet } = await import('vis-network/standalone');
      if (!containerRef.current) return;

      const nodes = new DataSet(NODES);
      const edges = new DataSet(EDGES.map((e, i) => ({ id: i, ...e })));
      network = new Network(containerRef.current, { nodes, edges }, OPTIONS);

      network.on('beforeDrawing', ctx => {
        LAYER_BANDS.forEach(({ label, group, bandMinX, bandMaxX, minY, maxY }) => {
          const { bg, border } = C[group];
          const w = bandMaxX - bandMinX;
          const h = maxY - minY;
          ctx.save();
          ctx.globalAlpha = 0.28;
          ctx.fillStyle = bg;
          drawRoundRect(ctx, bandMinX, minY, w, h, 12);
          ctx.fill();
          ctx.globalAlpha = 0.65;
          ctx.strokeStyle = border;
          ctx.lineWidth = 1.5;
          drawRoundRect(ctx, bandMinX, minY, w, h, 12);
          ctx.stroke();
          ctx.globalAlpha = 1;
          ctx.fillStyle = border;
          ctx.font = 'bold 11px ui-sans-serif, system-ui, sans-serif';
          ctx.fillText(label, bandMinX + 12, minY + 17);
          ctx.restore();
        });
      });

      network.fit({ animation: false });
    })();
    return () => network?.destroy();
  }, []);

  return (
    <div style={{ margin: '24px 0' }}>
      <div
        ref={containerRef}
        style={{ height: '820px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff', overflow: 'hidden' }}
      />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginTop: '10px', justifyContent: 'center' }}>
        {LEGEND.map(({ key, label }) => (
          <span key={key} style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.75rem', color: '#64748b' }}>
            <span style={{ width: 10, height: 10, borderRadius: '2px', background: C[key].border, flexShrink: 0 }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
