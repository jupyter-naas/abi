'use client';

import type { ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input, Select, Textarea } from '@/components/ui/input';
import { SettingsField, SettingsNotice, SettingsPageHeader, SettingsSection } from '@/components/settings/settings-ui';
import type { SkillScope } from '@/stores/skills';
import { SkillPackageContents, type SkillFileEditor } from './skill-package-contents';

/**
 * The registered skill page. Create mode uses this same header, overview,
 * contents tree, and instructions block with empty editable fields.
 */
export function SkillRecordView({
  title,
  subtitle,
  onBack,
  actions,
  builtin = false,
  builtinSlug = '',
  canModify,
  error,
  name,
  onNameChange,
  slug,
  onSlugChange,
  slugReadOnly = false,
  slugHint,
  description,
  onDescriptionChange,
  scope,
  onScopeChange,
  enabled,
  onEnabledChange,
  files,
  selectedPath,
  selectedText,
  onSelectFile,
  fileEditor,
  onAddFile,
  onRemoveFile,
  prompt,
  onPromptChange,
  promptPlaceholder,
}: {
  title: string;
  subtitle: ReactNode;
  onBack: () => void;
  actions: ReactNode;
  builtin?: boolean;
  builtinSlug?: string;
  canModify: boolean;
  error: string | null;
  name: string;
  onNameChange: (value: string) => void;
  slug: string;
  onSlugChange?: (value: string) => void;
  slugReadOnly?: boolean;
  slugHint?: string;
  description: string;
  onDescriptionChange: (value: string) => void;
  scope: SkillScope;
  onScopeChange: (value: SkillScope) => void;
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  files: string[];
  selectedPath: string | null;
  selectedText: string | null;
  onSelectFile: (path: string) => void;
  fileEditor?: SkillFileEditor | null;
  onAddFile?: (path: string) => string | null;
  onRemoveFile?: (path: string) => void;
  prompt: string;
  onPromptChange: (value: string) => void;
  promptPlaceholder?: string;
}) {
  return (
    <div className="space-y-6" data-testid="skill-record-view">
      <SettingsPageHeader
        leading={
          <Button
            variant="secondary"
            size="icon"
            className="h-9 w-9"
            onClick={onBack}
            title="Back to skills"
          >
            <ArrowLeft size={16} />
          </Button>
        }
        title={title}
        description={subtitle}
        actions={actions}
      />

      {builtin ? (
        <SettingsNotice>
          This skill is provided by an enabled module. Invoke it with /{builtinSlug}. Its package is read-only.
        </SettingsNotice>
      ) : (
        !canModify && <SettingsNotice>Only the creator can modify this private skill.</SettingsNotice>
      )}
      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}

      <SettingsSection title="Overview">
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-4">
            <SettingsField label="Name">
              <Input type="text" value={name} onChange={(e) => onNameChange(e.target.value)} disabled={!canModify} />
            </SettingsField>
            <SettingsField label="Slug" hint={slugHint}>
              <Input
                type="text"
                value={slug}
                onChange={(e) => onSlugChange?.(e.target.value)}
                disabled={!canModify || slugReadOnly}
                placeholder={slugReadOnly ? 'Created from the name' : undefined}
                className="font-mono"
              />
            </SettingsField>
          </div>
          <SettingsField label="Description">
            <Input
              type="text"
              value={description}
              onChange={(e) => onDescriptionChange(e.target.value)}
              disabled={!canModify}
            />
          </SettingsField>
          <div className="flex items-end gap-6">
            <SettingsField label="Visibility">
              <Select
                value={scope}
                onChange={(e) => onScopeChange(e.target.value as SkillScope)}
                disabled={!canModify}
                className="w-auto"
              >
                {builtin && <option value="builtin">Module</option>}
                <option value="user">Private (only me)</option>
                <option value="workspace">Workspace</option>
                <option value="organization">Organization</option>
              </Select>
            </SettingsField>
            <Checkbox
              checked={enabled}
              onCheckedChange={onEnabledChange}
              disabled={!canModify}
              label="Enabled"
              className="h-9"
            />
          </div>
        </div>
      </SettingsSection>

      <SkillPackageContents
        files={files}
        selectedPath={selectedPath}
        selectedText={selectedText}
        onSelect={onSelectFile}
        fileEditor={fileEditor}
        onAddFile={onAddFile}
        onRemoveFile={onRemoveFile}
      />

      <SettingsSection title="Instructions" description="The prompt applied when this skill is invoked.">
        <Textarea
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          disabled={!canModify}
          placeholder={promptPlaceholder}
          rows={12}
        />
      </SettingsSection>
    </div>
  );
}
