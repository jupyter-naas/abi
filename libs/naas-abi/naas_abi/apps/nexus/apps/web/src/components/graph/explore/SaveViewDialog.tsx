'use client'

import { useState } from 'react'
import { Loader2, X } from 'lucide-react'

export interface SaveViewDialogProps {
  initialName?: string
  initialPath?: string
  initialDescription?: string
  knownFolders: string[]
  saving: boolean
  error: string | null
  onCancel: () => void
  onSave: (name: string, path: string, description: string) => void
}

/** Modal to name + describe + file a saved Explore view under a folder path. */
export function SaveViewDialog({
  initialName = '',
  initialPath = '',
  initialDescription = '',
  knownFolders,
  saving,
  error,
  onCancel,
  onSave,
}: SaveViewDialogProps) {
  const [name, setName] = useState(initialName)
  const [path, setPath] = useState(initialPath)
  const [description, setDescription] = useState(initialDescription)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" data-testid="save-view-dialog">
      <div className="w-[420px] rounded-lg border bg-background p-4 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Save view</h2>
          <button onClick={onCancel} className="rounded p-1 hover:bg-muted" aria-label="Close">
            <X size={14} />
          </button>
        </div>

        <label className="mb-3 block">
          <span className="mb-1 block text-xs font-medium text-muted-foreground">Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Solitude × Sport extractions"
            data-testid="save-view-name"
            autoFocus
            className="w-full rounded border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary"
          />
        </label>

        <label className="mb-3 block">
          <span className="mb-1 block text-xs font-medium text-muted-foreground">
            Description <span className="font-normal">(optional — what question does this view answer?)</span>
          </span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. Which extractions link a Solitude disposition to a Sport process?"
            data-testid="save-view-description"
            rows={3}
            className="w-full resize-y rounded border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary"
          />
        </label>

        <label className="mb-3 block">
          <span className="mb-1 block text-xs font-medium text-muted-foreground">
            Folder <span className="font-normal">(optional, e.g. Research/PHASES)</span>
          </span>
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="Research/PHASES"
            list="explore-folder-suggestions"
            data-testid="save-view-path"
            className="w-full rounded border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary"
          />
          <datalist id="explore-folder-suggestions">
            {knownFolders.map((f) => (
              <option key={f} value={f} />
            ))}
          </datalist>
        </label>

        {error && <p className="mb-2 text-xs text-destructive">{error}</p>}

        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="rounded border px-3 py-1.5 text-xs hover:bg-muted">
            Cancel
          </button>
          <button
            onClick={() => onSave(name.trim(), path.trim(), description.trim())}
            disabled={saving || name.trim().length === 0}
            data-testid="save-view-confirm"
            className="flex items-center gap-1 rounded bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {saving && <Loader2 size={12} className="animate-spin" />}
            Save
          </button>
        </div>
      </div>
    </div>
  )
}
