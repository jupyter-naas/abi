import { describe, expect, it } from 'vitest';
import { chatRosterSections, partitionChatRosterAgents } from './chat-section-agents';

const axi = {
  id: 'axi',
  isDefault: true,
  class_name: 'axi.agents.AxiAgent/AxiAgent',
};
const osint = {
  id: 'osint',
  isDefault: false,
  class_name: 'logistics.devops.agents.OsintAgent/OsintAgent',
};
const abi = {
  id: 'abi',
  isDefault: false,
  class_name: 'naas_abi.agents.AbiAgent/AbiAgent',
};
const apps = {
  id: 'apps',
  isDefault: false,
  class_name: 'naas_abi.agents.AppsAgent/AppsAgent',
};
const manual = { id: 'manual', isDefault: false, class_name: null };

describe('partitionChatRosterAgents', () => {
  it('packs the naas_abi agents and previews the rest', () => {
    const { preview, packed } = partitionChatRosterAgents([axi, apps, osint, abi]);

    expect(preview.map((a) => a.id)).toEqual(['axi', 'osint']);
    expect(packed.map((a) => a.id)).toEqual(['apps', 'abi']);
  });

  it('keeps the workspace default in the preview even when it is Abi', () => {
    const abiDefault = { ...abi, isDefault: true };
    const { preview, packed } = partitionChatRosterAgents([abiDefault, apps, osint]);

    expect(preview.map((a) => a.id)).toEqual(['abi', 'osint']);
    expect(packed.map((a) => a.id)).toEqual(['apps']);
  });

  it('previews agents from other modules and hand-made ones', () => {
    const lookalike = {
      id: 'acme',
      isDefault: false,
      class_name: 'acme.agents.AppsAgent/AppsAgent',
    };
    const { preview, packed } = partitionChatRosterAgents([lookalike, manual]);

    expect(preview.map((a) => a.id)).toEqual(['acme', 'manual']);
    expect(packed).toEqual([]);
  });

  it('preserves the incoming order inside each half', () => {
    const { preview, packed } = partitionChatRosterAgents([
      osint,
      abi,
      axi,
      apps,
    ]);

    expect(preview.map((a) => a.id)).toEqual(['osint', 'axi']);
    expect(packed.map((a) => a.id)).toEqual(['abi', 'apps']);
  });
});

describe('chatRosterSections', () => {
  // The dcg-pilot roster after sync, in the order chat-section.tsx sorts it:
  // default first, then last-used, then name. Abi is on it unconditionally.
  const roster = [
    { id: 'Axi Agent', isDefault: true, class_name: 'axi.agents.AxiAgent/AxiAgent' },
    { id: 'Abi', isDefault: false, class_name: 'naas_abi.agents.AbiAgent/AbiAgent' },
    {
      id: 'Agent Catalog',
      isDefault: false,
      class_name: 'naas_abi.agents.AgentCatalogAgent/AgentCatalogAgent',
    },
    { id: 'Apps', isDefault: false, class_name: 'naas_abi.agents.AppsAgent/AppsAgent' },
    {
      id: 'Counter-UAS Report',
      isDefault: false,
      class_name: 'operations.report.agents.ReportAgent/ReportAgent',
    },
    { id: 'Files', isDefault: false, class_name: 'naas_abi.agents.FilesAgent/FilesAgent' },
    {
      id: 'Knowledge Graph',
      isDefault: false,
      class_name: 'naas_abi.agents.KnowledgeGraphAgent/KnowledgeGraphAgent',
    },
    { id: 'Ontology', isDefault: false, class_name: 'naas_abi.agents.OntologyAgent/OntologyAgent' },
    {
      id: 'Osint Agent',
      isDefault: false,
      class_name: 'logistics.devops.agents.OsintAgent/OsintAgent',
    },
    { id: 'Settings', isDefault: false, class_name: 'naas_abi.agents.SettingsAgent/SettingsAgent' },
    {
      id: 'Summary Text Agent',
      isDefault: false,
      class_name: 'operations.report.agents.SummaryTextAgent/SummaryTextAgent',
    },
  ];

  it('collapses a real roster to the agents you chat with', () => {
    const { visible, hiddenCount } = chatRosterSections(roster, false);

    expect(visible.map((a) => a.id)).toEqual([
      'Axi Agent',
      'Counter-UAS Report',
      'Osint Agent',
      'Summary Text Agent',
    ]);
    expect(hiddenCount).toBe(7);
  });

  it('appends the packed half on expand, never reordering the preview', () => {
    const { visible, hiddenCount } = chatRosterSections(roster, true);

    expect(visible.map((a) => a.id)).toEqual([
      'Axi Agent',
      'Counter-UAS Report',
      'Osint Agent',
      'Summary Text Agent',
      'Abi',
      'Agent Catalog',
      'Apps',
      'Files',
      'Knowledge Graph',
      'Ontology',
      'Settings',
    ]);
    expect(visible).toHaveLength(roster.length);
    // Unchanged while expanded so the toggle can render "Show less".
    expect(hiddenCount).toBe(7);
  });

  it('still caps the preview when the roster is all chat agents', () => {
    const many = Array.from({ length: 8 }, (_, i) => ({
      id: `a${i}`,
      isDefault: i === 0,
      class_name: `acme.agents.A${i}/A${i}`,
    }));
    const { visible, hiddenCount } = chatRosterSections(many, false);

    expect(visible.map((a) => a.id)).toEqual(['a0', 'a1', 'a2', 'a3', 'a4']);
    expect(hiddenCount).toBe(3);
  });

  it('has nothing to hide when every agent fits the preview', () => {
    const { visible, hiddenCount } = chatRosterSections([axi, osint], false);

    expect(visible.map((a) => a.id)).toEqual(['axi', 'osint']);
    expect(hiddenCount).toBe(0);
  });
});
