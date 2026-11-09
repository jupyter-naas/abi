import { describe, expect, it } from 'vitest';
import {
  PLATFORM,
  encodeSegment,
  organizationContainer,
  parseScope,
  workspaceContainer,
} from './access-scope';

describe('container names', () => {
  it('writes container ids as one encoded segment', () => {
    expect(encodeSegment('a b/c:d*')).toBe('a%20b%2Fc%3Ad%2A');
    expect(encodeSegment("x!'()~.-_")).toBe('x%21%27%28%29~.-_');
    expect(organizationContainer('o/1')).toBe('abi:nexus:organization/o%2F1');
    expect(workspaceContainer('o', 'w 1')).toBe('abi:nexus:organization/o/nexus:workspace/w%201');
    expect(workspaceContainer(null, 'w')).toBe('abi:nexus:workspace/w');
  });

  it('reads a scope back into its containers', () => {
    expect(parseScope(PLATFORM)).toEqual({ containers: [], below: false });
    expect(parseScope('abi:nexus:organization/acme/nexus:workspace/ws%201')).toEqual({
      containers: [
        { service: 'nexus', type: 'organization', id: 'acme' },
        { service: 'nexus', type: 'workspace', id: 'ws 1' },
      ],
      below: false,
    });
    expect(parseScope('abi:nexus:organization/acme/*')).toEqual({
      containers: [{ service: 'nexus', type: 'organization', id: 'acme' }],
      below: true,
    });
    expect(parseScope(null)).toBeNull();
    expect(parseScope('abi:-:-')).toBeNull();
    expect(parseScope('abi:acme:ws-1')).toBeNull();
    expect(parseScope('abi:triple_store:graph/a/b')).toBeNull();
    expect(parseScope('abi:*/nexus:workspace/w')).toBeNull();
  });
});
