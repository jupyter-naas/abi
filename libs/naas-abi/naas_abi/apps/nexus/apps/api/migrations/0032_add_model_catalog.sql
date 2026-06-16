-- Migration: Persistent store for marketplace AI model display properties.
-- Date: 2026-06-15
--
-- The catalog is discovered statically from naas_abi_marketplace.ai.*/models/*.py.
-- This table mirrors each model so its display properties (name, description,
-- image, context_window) can be edited from the frontend and survive restarts.
--
-- The `source_*` columns hold the last value seen in the Python source so we can
-- detect when a property changes in code. `overridden_fields` is a JSON array of
-- the property names a user edited in the frontend; those are NOT overwritten by
-- a later source change (a warning is logged instead).

CREATE TABLE IF NOT EXISTS model_catalog (
    canonical_id VARCHAR(255) PRIMARY KEY,
    model_id VARCHAR(255) NOT NULL,
    provider VARCHAR(255) NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    module_path VARCHAR(512) NOT NULL,

    -- Effective (served) display values.
    name TEXT,
    description TEXT,
    image TEXT,
    context_window INTEGER,

    -- Last-known values from the Python source (for change detection).
    source_name TEXT,
    source_description TEXT,
    source_image TEXT,
    source_context_window INTEGER,

    -- JSON array of property names edited in the frontend.
    overridden_fields TEXT NOT NULL DEFAULT '[]',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_model_catalog_provider_id ON model_catalog(provider_id);
CREATE INDEX IF NOT EXISTS idx_model_catalog_model_id ON model_catalog(model_id);
