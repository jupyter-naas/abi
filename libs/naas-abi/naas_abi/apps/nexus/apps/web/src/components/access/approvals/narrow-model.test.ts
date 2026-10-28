import { describe, expect, it } from 'vitest';
import type { PolicyDocument } from '@/lib/iam-admin/types';
import {
  initialChoice,
  isUnchanged,
  narrowed,
  problem,
  summarize,
  summaryText,
  toggleAction,
  toggleResource,
} from './narrow-model';

const document: PolicyDocument = {
  version: '2026-10-13',
  statements: [
    { sid: 'Read', effect: 'Allow', actions: ['triple_store:Query', 'triple_store:ListGraphs'], resources: ['abi:-:-:triple_store:graph/a', 'abi:-:-:triple_store:graph/b'] },
    { effect: 'Deny', actions: ['triple_store:DropGraph'], resources: ['*'] },
    { effect: 'Allow', actions: ['event:Publish'], resources: ['abi:-:-:event:type/x'] },
  ],
};

describe('narrow model', () => {
  it('keeps everything at first, which is the plain approval', () => {
    const choice = initialChoice(document);
    expect(isUnchanged(document, choice)).toBe(true);
    expect(narrowed(document, choice)).toEqual(document);
    expect(summaryText(summarize(document, choice))).toBe('Approved as submitted.');
  });

  it('removes unchecked actions and resources, in submitted order', () => {
    let choice = initialChoice(document);
    choice = toggleAction(choice, 0, 'triple_store:ListGraphs');
    choice = toggleResource(choice, 0, 'abi:-:-:triple_store:graph/b');
    const result = narrowed(document, choice);
    expect(isUnchanged(document, choice)).toBe(false);
    expect(result.statements[0]).toEqual({
      sid: 'Read',
      effect: 'Allow',
      actions: ['triple_store:Query'],
      resources: ['abi:-:-:triple_store:graph/a'],
    });
    expect(summaryText(summarize(document, choice))).toBe(
      '1 of 3 actions removed, 1 of 3 resources removed',
    );
  });

  it('never touches a Deny statement', () => {
    let choice = initialChoice(document);
    choice = toggleAction(choice, 1, 'triple_store:DropGraph');
    choice = toggleResource(choice, 1, '*');
    expect(narrowed(document, choice).statements[1]).toEqual(document.statements[1]);
    expect(isUnchanged(document, choice)).toBe(true);
  });

  it('drops an Allow statement left with no action or no resource', () => {
    let choice = initialChoice(document);
    choice = toggleAction(choice, 2, 'event:Publish');
    const result = narrowed(document, choice);
    expect(result.statements.map((s) => s.effect + ':' + s.actions[0])).toEqual([
      'Allow:triple_store:Query',
      'Deny:triple_store:DropGraph',
    ]);
    expect(summarize(document, choice).statementsDropped).toBe(1);
    expect(summaryText(summarize(document, choice))).toContain('1 statement dropped');
  });

  it('refuses a selection that grants nothing', () => {
    let choice = initialChoice(document);
    choice = toggleAction(choice, 0, 'triple_store:Query');
    choice = toggleAction(choice, 0, 'triple_store:ListGraphs');
    choice = toggleAction(choice, 2, 'event:Publish');
    expect(problem(document, choice)).toMatch(/reject/);
    expect(problem(document, initialChoice(document))).toBeNull();
  });

  it('can put a removed action back', () => {
    let choice = toggleAction(initialChoice(document), 0, 'triple_store:Query');
    choice = toggleAction(choice, 0, 'triple_store:Query');
    expect(isUnchanged(document, choice)).toBe(true);
  });
});
