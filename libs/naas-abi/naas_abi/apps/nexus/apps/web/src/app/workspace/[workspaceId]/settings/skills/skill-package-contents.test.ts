import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { SkillPackageContents } from './skill-package-contents';

const sheetsFiles = [
  'SKILL.md',
  'references/research.md',
  'scripts/validate_workbook.py',
];

describe('SkillPackageContents', () => {
  it('renders folders and shows the selected markdown body', () => {
    const html = renderToStaticMarkup(
      createElement(SkillPackageContents, {
        files: sheetsFiles,
        selectedPath: 'references/research.md',
        selectedText: '# Research\n\n- Nexus renders the grid from the JSON model.\n',
        onSelect: () => {},
      }),
    );

    expect(html).toContain('Contents');
    expect(html).toContain('· 3');
    const skillAt = html.indexOf('data-path="SKILL.md"');
    const referencesAt = html.indexOf('data-folder="references"');
    const scriptsAt = html.indexOf('data-folder="scripts"');
    expect(skillAt).toBeGreaterThan(-1);
    expect(referencesAt).toBeGreaterThan(skillAt);
    expect(scriptsAt).toBeGreaterThan(referencesAt);
    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain('research.md');
    expect(html).toContain('validate_workbook.py');
    expect(html).toContain('references/research.md');
    expect(html).toContain('<h1>Research</h1>');
    expect(html).toContain('<li>Nexus renders the grid from the JSON model.</li>');
    expect(html).toContain('data-testid="skill-file-body"');
  });

  it('shows a python file as code text', () => {
    const html = renderToStaticMarkup(
      createElement(SkillPackageContents, {
        files: sheetsFiles,
        selectedPath: 'scripts/validate_workbook.py',
        selectedText: 'def main() -> int:\n    return 1\n',
        onSelect: () => {},
      }),
    );

    expect(html).toContain('<pre');
    expect(html).toContain('def main() -&gt; int:');
    expect(html).not.toContain('<h1');
  });

  it('renders nothing for a prompt row with no files', () => {
    const html = renderToStaticMarkup(
      createElement(SkillPackageContents, {
        files: [],
        selectedPath: null,
        selectedText: null,
        onSelect: () => {},
      }),
    );
    expect(html).toBe('');
  });
});
