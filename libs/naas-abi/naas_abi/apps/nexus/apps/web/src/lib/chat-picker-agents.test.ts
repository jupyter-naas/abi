import { describe, expect, it } from 'vitest';
import { chatPickerAgents } from './chat-picker-agents';

const joe = { id: 'joe', inChatPicker: true };
const abi = { id: 'abi', inChatPicker: false };
const files = { id: 'files', inChatPicker: false };
const remote = { id: 'remote' };

describe('chatPickerAgents', () => {
  it('leaves out the agents the workspace default fronts', () => {
    expect(chatPickerAgents([joe, abi, files, remote]).map((a) => a.id)).toEqual([
      'joe',
      'remote',
    ]);
  });

  it('offers every agent when the API marks none', () => {
    const roster = [{ id: 'abi' }, { id: 'apps' }, { id: 'acme', inChatPicker: true }];
    expect(chatPickerAgents(roster)).toEqual(roster);
  });

  it('keeps the agents a pane runs, in roster order', () => {
    expect(chatPickerAgents([abi, joe, files], ['files', null, undefined]).map((a) => a.id)).toEqual([
      'joe',
      'files',
    ]);
  });
});
