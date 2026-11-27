'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input, Textarea } from '@/components/ui/input'
import { Notice } from '@/components/ui/notice'
import { Spinner } from '@/components/ui/spinner'

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
  const ready = !saving && name.trim().length > 0
  const save = () => {
    if (ready) onSave(name.trim(), path.trim(), description.trim())
  }

  return (
    <Dialog
      title="Save view"
      onClose={onCancel}
      onSubmit={save}
      data-testid="save-view-dialog"
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={save} disabled={!ready} data-testid="save-view-confirm">
            {saving && <Spinner size={12} />}
            Save
          </Button>
        </>
      }
    >
      <Field label="Name" htmlFor="save-view-name">
        <Input
          id="save-view-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Solitude × Sport extractions"
          data-testid="save-view-name"
          data-autofocus
        />
      </Field>
      <Field label="Description" hint="Optional — what question does this view answer?" htmlFor="save-view-description">
        <Textarea
          id="save-view-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. Which extractions link a Solitude disposition to a Sport process?"
          data-testid="save-view-description"
          rows={3}
        />
      </Field>
      <Field label="Folder" hint="Optional, e.g. Research/PHASES" htmlFor="save-view-path">
        <Input
          id="save-view-path"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="Research/PHASES"
          list="explore-folder-suggestions"
          data-testid="save-view-path"
        />
        <datalist id="explore-folder-suggestions">
          {knownFolders.map((f) => (
            <option key={f} value={f} />
          ))}
        </datalist>
      </Field>
      {error && <Notice tone="error">{error}</Notice>}
    </Dialog>
  )
}
