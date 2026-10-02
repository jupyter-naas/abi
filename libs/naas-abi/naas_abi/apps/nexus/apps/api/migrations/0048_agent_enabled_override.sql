-- A user's explicit enable/disable of an agent. Workspace sync keeps it over the
-- `agents:` roster from config (which then only decides the default).
-- NULL = never toggled by hand: follow the roster.
ALTER TABLE agent_configs
    ADD COLUMN IF NOT EXISTS enabled_override BOOLEAN;
