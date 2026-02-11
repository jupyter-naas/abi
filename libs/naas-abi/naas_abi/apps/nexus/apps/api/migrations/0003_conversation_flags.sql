-- Migration: Add pinned and archived flags to conversations
-- Date: 2026-02-09

-- Add pinned column
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT false;

-- Add archived column
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false;

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_conversations_pinned ON conversations(pinned);
CREATE INDEX IF NOT EXISTS idx_conversations_archived ON conversations(archived);
