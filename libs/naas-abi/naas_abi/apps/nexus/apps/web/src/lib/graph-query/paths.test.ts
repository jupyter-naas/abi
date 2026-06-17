import { describe, expect, it } from 'vitest'
import { buildColumnsPath, buildListViewsPath, foldersPath, viewPath } from './paths'

describe('buildColumnsPath', () => {
  it('repeats graph_uri and class_uri params', () => {
    const path = buildColumnsPath({
      workspaceId: 'ws-1',
      graphUris: ['http://g/a', 'http://g/b'],
      classUris: ['http://c/Person'],
    })
    expect(path.startsWith('/api/graph/columns?')).toBe(true)
    const qs = new URLSearchParams(path.split('?')[1])
    expect(qs.get('workspace_id')).toBe('ws-1')
    expect(qs.getAll('graph_uri')).toEqual(['http://g/a', 'http://g/b'])
    expect(qs.getAll('class_uri')).toEqual(['http://c/Person'])
  })
})

describe('buildListViewsPath', () => {
  it('omits path/recursive when not provided', () => {
    const qs = new URLSearchParams(buildListViewsPath({ workspaceId: 'ws-1' }).split('?')[1])
    expect(qs.get('workspace_id')).toBe('ws-1')
    expect(qs.has('path')).toBe(false)
    expect(qs.has('recursive')).toBe(false)
  })
  it('includes an empty path (root) and recursive flag', () => {
    const qs = new URLSearchParams(
      buildListViewsPath({ workspaceId: 'ws-1', path: '', recursive: true }).split('?')[1],
    )
    expect(qs.get('path')).toBe('')
    expect(qs.get('recursive')).toBe('true')
  })
})

describe('viewPath / foldersPath', () => {
  it('encodes the view id and appends workspace_id', () => {
    expect(viewPath('a b/c')).toBe('/api/view/a%20b%2Fc')
    const withWs = viewPath('v1', 'ws-1')
    expect(withWs).toBe('/api/view/v1?workspace_id=ws-1')
  })
  it('builds the folders path', () => {
    expect(foldersPath('ws-1')).toBe('/api/view/folders?workspace_id=ws-1')
  })
})
