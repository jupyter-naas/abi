import { describe, expect, it } from 'vitest';
import {
  DEFAULT_VISIBLE_COLUMNS,
  MODEL_EXPORT_HEADERS,
  formatContext,
  modelCellValues,
  modelExportRow,
  modelRows,
  modelSearchTexts,
  modelSortValue,
  visibleColumnsFrom,
  type Model,
  type Provider,
} from './models-panel-model';

const model = (over: Partial<Model>): Model => ({
  canonical_id: 'openai/gpt-x',
  model_id: 'gpt-x',
  provider: 'openai',
  provider_id: 'openai',
  module_path: 'naas_abi_marketplace.ai.chatgpt',
  configured: true,
  name: 'GPT X',
  description: 'A model',
  image: null,
  context_window: 128000,
  ...over,
});
const OPENAI: Provider = {
  id: 'openai',
  name: 'OpenAI',
  module_path: 'naas_abi_marketplace.ai.chatgpt',
  configured: true,
  logo_url: null,
  config_keys: [],
  models: [],
};

describe('the models table', () => {
  it('names each model its provider, else the provider the catalog gives', () => {
    const [known, unknown] = modelRows([model({}), model({ provider_id: 'acme', provider: 'acme' })], [OPENAI]);
    expect(known.provider_name).toBe('OpenAI');
    expect(unknown.provider_name).toBe('acme');
  });

  it('gives each column the values its filter sees', () => {
    const [row] = modelRows([model({})], [OPENAI]);
    expect(modelCellValues(row, 'name')).toEqual(['GPT X']);
    expect(modelCellValues(row, 'provider')).toEqual(['OpenAI']);
    expect(modelCellValues(row, 'context_window')).toEqual(['128K']);
    expect(modelCellValues(row, 'status')).toEqual(['Configured']);
    expect(modelCellValues(row, 'image')).toEqual([]);
    const [bare] = modelRows([model({ name: null, configured: false, description: null })], [OPENAI]);
    expect(modelCellValues(bare, 'name')).toEqual(['openai/gpt-x']);
    expect(modelCellValues(bare, 'status')).toEqual(['Not configured']);
    expect(modelCellValues(bare, 'description')).toEqual(['']);
  });

  it('sorts the context by size, an unknown one first', () => {
    const [big, small, none] = modelRows(
      [model({ context_window: 128000 }), model({ context_window: 8000 }), model({ context_window: null })],
      [OPENAI],
    );
    expect([big, small, none].map((row) => modelSortValue(row, 'context_window'))).toEqual([128000, 8000, -1]);
    expect(modelSortValue(big, 'provider')).toBe('OpenAI');
  });

  it('searches the ids, the name and the provider', () => {
    const [row] = modelRows([model({})], [OPENAI]);
    expect(modelSearchTexts(row)).toEqual(['openai/gpt-x', 'gpt-x', 'openai', 'openai', 'OpenAI', 'GPT X']);
  });

  it('formats the context window', () => {
    expect(formatContext(null)).toBe('—');
    expect(formatContext(512)).toBe('512');
    expect(formatContext(200000)).toBe('200K');
  });

  it('keeps the known columns of a stored choice, else the defaults', () => {
    expect(visibleColumnsFrom(['name', 'nope', 'status'])).toEqual(['name', 'status']);
    expect(visibleColumnsFrom(['nope'])).toEqual(DEFAULT_VISIBLE_COLUMNS);
    expect(visibleColumnsFrom('garbage')).toEqual(DEFAULT_VISIBLE_COLUMNS);
  });

  it('exports every column but the image, the context as a number', () => {
    const [row] = modelRows([model({})], [OPENAI]);
    expect(MODEL_EXPORT_HEADERS).toEqual([
      'Name',
      'Model ID',
      'Canonical ID',
      'Provider',
      'Provider ID',
      'Module path',
      'Description',
      'Context',
      'Status',
    ]);
    expect(modelExportRow(row)).toEqual([
      'GPT X',
      'gpt-x',
      'openai/gpt-x',
      'OpenAI',
      'openai',
      'naas_abi_marketplace.ai.chatgpt',
      'A model',
      '128000',
      'Configured',
    ]);
  });
});
